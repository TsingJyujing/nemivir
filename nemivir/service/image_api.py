import gc
import logging
import socket
import time
import traceback
from io import BytesIO
from typing import List

from PIL import Image
from fastapi import FastAPI, File, UploadFile
from prometheus_client import CollectorRegistry, multiprocess, generate_latest, Counter
from redlock import Redlock
from requests import HTTPError, Response
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from nemivir.config import filer_server, redis_connection_pool, cache
from nemivir.image import get_hash
from nemivir.util import RedisDistributedLock, get_random_string, LazyResource

app = FastAPI(
    title="Nemivir Image Database",
    version="0.1",
    description="A unique image database based on rocksdb and seaweedfs: "
                "<a href=\"https://github.com/TsingJyujing/nemivir\">Source Code</a>"
)

log = logging.getLogger(__file__)

request_count = Counter(
    "api_request_count",
    "Request Count of API",
    labelnames=("api_name",)
)

fail_count = Counter(
    "api_fail_count",
    "Fail Count of API",
    labelnames=("status_code", "exception_type")
)


class ParameterError(Exception): pass


@app.get("/")
def read_root():
    """
    Got to document
    """
    return RedirectResponse(
        "/docs"
    )


@app.get("/health")
def health():
    """
    Health check interface
    """
    return {"status": "success"}


@app.post("/system/gc")
def system_gc(generation: int = 2):
    """
    GC
    :param generation:
    :return:
    """
    gc.collect(generation=generation)
    return {"status": "success"}


@app.get("/metrics")
def metrics():
    """
    Prometheus metrics export
    """
    request_count.labels("metrics").inc()
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return generate_latest(registry)


@app.exception_handler(HTTPError)
async def requests_http_error_handler(request: Request, exc: HTTPError):
    response: Response = exc.response
    status_code = response.status_code
    fail_count.labels(status_code, str(type(exc))).inc()
    log.error("An HTTP error caused by requesting other resources.", exc)
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "fail",
            "message": "Error while requesting other resources.",
            "status_code": status_code,
            "resource": response.url,
        }
    )


@app.exception_handler(ParameterError)
async def requests_http_error_handler(request: Request, exc: ParameterError):
    fail_count.labels(422, str(type(exc))).inc()
    return JSONResponse(
        status_code=422,
        content={
            "status": "fail",
            "message": str(exc),
        }
    )


@app.exception_handler(Exception)
async def requests_http_error_handler(request: Request, exc: Exception):
    fail_count.labels(500, str(type(exc))).inc()
    log.error("Some internal error caused: {}".format(
        traceback.format_exc()
    ))
    return JSONResponse(
        status_code=500,
        content={
            "status": "fail",
            "message": str(exc),
        }
    )


@app.get("/list/hash")
def list_hashes(limit: int = 1000):
    """
    Get all hashes information
    - **limit**: Limit the number of the return
    """
    request_count.labels("list_hashes").inc()
    return {
        "status": "success",
        "hashes": filer_server.list_dirs("/", limit)
    }


@app.get("/list/image/{image_hash}")
def list_images(image_hash: str, limit: int = 1000):
    """
    Get all images info in a hash
    - **image_hash**: Image hash info
    - **limit**: Limit the number of the return
    """
    request_count.labels("list_images").inc()
    return filer_server.list_images("/{}".format(image_hash), limit)


@app.get("/image/{image_hash}/{filename}")
def get_specified_image(
        image_hash: str,
        filename: str,
        rescale: float = None,
        h: int = None,
        w: int = None,
        image_format: str = None
):
    """
    Get a image name by specified filename
    - **image_hash**: Image hash
    - **filename**: file name under the hash
    - **rescale**:  resize image by ratio (0.0~1.0) before response, don't input means don't apply change
    - **h**:  resize image by height and width
    - **w**:  resize image by height and width
    - **image_format**:  the image format to return, WEBP/PNG/JPG/...
    """
    request_count.labels("get_specified_image").inc()
    return __get_image_cache(
        filename="{}/{}".format(image_hash, filename),
        rescale=rescale, h=h, w=w,
        image_format=image_format,
    )


@app.get("/hash/{image_hash}")
def get_one_image_by_hash(
        image_hash: str,
        rescale: float = None,
        h: int = None,
        w: int = None,
        image_format: str = None
):
    """
    Get a image by hash
    - **image_hash**: Image hash
    - **rescale**:  resize image by ratio (0.0~1.0) before response, don't input means don't apply change
    - **h**:  resize image by height and width
    - **w**:  resize image by height and width
    - **image_format**:  the image format to return, WEBP/PNG/JPG/...
    """
    request_count.labels("get_one_image_by_hash").inc()
    return __get_image_cache(
        filename=filer_server.list_images(image_hash, 1)[0]["FullPath"].strip("/"),
        rescale=rescale, h=h, w=w,
        image_format=image_format,
    )


@app.delete("/image/{image_hash}/{filename}")
def delete_specified_image(
        image_hash: str,
        filename: str
):
    """
    Remove the image by filename
    - **image_hash**: Image hash
    - **filename**: file name under the hash
    """
    request_count.labels("delete_specified_image").inc()
    filer_server.delete_file("{}/{}".format(image_hash, filename))
    cache.clean("{}/{}".format(image_hash, filename))
    return {"status": "success"}


@app.delete("/hash/{image_hash}")
def delete_images_by_hash(
        image_hash: str
):
    """
    Remove all image under specified hash
    - **image_hash**: Image hash
    """
    request_count.labels("delete_images_by_hash").inc()
    filer_server.delete_dir(
        image_hash,
        recursive=True,
        ignore_recursive_error=True
    )
    cache.clean_hash(image_hash)
    return {"status": "success"}


def __get_image_cache(
        filename: str,
        rescale: float,
        h: int,
        w: int,
        image_format: str
):
    request_count.labels("__get_image_cache").inc()

    param_key = "({},{},{},{})".format(
        image_format,
        w if w else "-",
        h if h else "-",
        "{:.3f}".format(rescale) if rescale else "-"
    )

    try:
        data = cache.get(filename, key=param_key)
        log.info("Hit cache on KEY {}_{}".format(filename, param_key))
    except KeyError:
        data = __get_image(
            filename,
            rescale,
            h,
            w,
            image_format
        )
        log.info("Create cache on KEY {}_{}".format(filename, param_key))
        cache.put(filename, param_key, data)
    return Response(
        content=data,
        status_code=200,
        media_type="image"
    )


def __get_image(
        filename: str,
        rescale: float,
        h: int,
        w: int,
        image_format: str
):
    """
    Image resource
    - **filename**:
    - **image_hash**:
    - **rescale**:  Zoom image before response
    - **h**:  Height limit
    - **w**:  Width limit
    - **image_format**:  The image format to return, none means using original format
    """
    request_count.labels("__get_image").inc()

    # Parameter verify
    if rescale is not None and (rescale > 1.0 or rescale <= 0):
        raise ParameterError("Invalid value rescale={}".format(rescale))

    if (w is None) != (h is None):
        raise ParameterError("Parameter w and h should appeared at same time!")

    if rescale is not None and w is not None:
        raise ParameterError("Parameter rescale/(w&h) are mutually exclusive.")

    data = filer_server.read_file(filename)

    with BytesIO(data) as bio:
        im = Image.open(bio)

        if image_format is None:
            image_final_format = im.format.lower()
        else:
            image_final_format = image_format.lower()
        # FIXME serialize media type in cache
        # media_type = "image/{}".format(image_final_format)
        need_transform = not (image_format is None or (image_format.upper() == im.format))

        need_rescale = rescale is not None
        need_resize = h is not None and w is not None

        # FIXME for now we can't deal with the animated image
        if getattr(im, "is_animated", False):
            need_transform = False
            need_rescale = False
            need_resize = False
        if not need_transform and not need_rescale and not need_resize:
            return data

        # Apply resize stage by parameters
        if rescale is not None:
            new_size = round(im.size[0] * rescale), round(im.size[1] * rescale)
            im = im.resize(size=new_size)
        elif h is not None and w is not None:
            im = im.resource.resize(
                size=(w, h)
            )
        if image_final_format == "JPEG":
            im = im.convert("RGB")
        with BytesIO() as fp:
            im.save(fp, format=image_final_format)
            fp.seek(0)
            data = fp.read()
        return data


@app.post("/upload")
def upload_image(
        file: UploadFile = File(...),
        mode: str = "keep",
        auto_remove: bool = False,
        image_format: str = "original",
        method: int = 6,
        lossless: bool = False,
        quality: int = 80,
):
    """
    Upload a new image
    - **file**: Upload image file
    - **mode**:
        - `keep`: keep image anyway (default), will create a new file
        - `block`: don't save if image already existed
        - `largest`: if largest (evaluated by width x height) then save a new file
    - **auto_remove**: after saving this image, remove other image in the same slot
    - **to_webp**: auto trans-format to webp

    **These parameters only works while to_webp is true**

    - **method**: Compress method from 0~6, 0 is fastest and 6 is slowest
    - **lossless**: lossless=true will make file large
    - **quality**: 0~100, default is 80, a good trade-off between size and quality
    """
    request_count.labels("upload_image").inc()
    return __commit_image_file(
        file.file.read(),
        mode,
        auto_remove,
        image_format,
        method,
        lossless,
        quality
    )


@app.post("/batch_upload", deprecated=True)
def batch_upload_image(
        files: List[UploadFile] = File(...),
        mode: str = "keep",
        auto_remove: bool = False,
        image_format: str = "original",
        method: int = 6,
        lossless: bool = False,
        quality: int = 80,
):
    """
    Upload new images
    - **file**: Upload image file
    - **mode**:
        - `keep`: keep image anyway (default), will create a new file
        - `block`: don't save if image already existed
        - `largest`: if largest (evaluated by width x height) then save a new file
    - **auto_remove**: after saving this image, remove other image in the same slot
    - **to_webp**: auto trans-format to webp

    **These parameters only works while to_webp is true**

    - **method**: Compress method from 0~6, 0 is fastest and 6 is slowest
    - **lossless**: lossless=true will make file large
    - **quality**: 0~100, default is 80, a good trade-off between size and quality
    """
    request_count.labels("batch_upload_image").inc()
    response_all = []
    for file in files:
        try:
            response_all.append(__commit_image_file(
                file.file.read(),
                mode,
                auto_remove,
                image_format,
                method,
                lossless,
                quality
            ))
        except Exception as ex:
            response_all.append({
                "status": "fail"
            })
            log.error("Error while processing file in batch.", ex)
    return {
        "status": "success",
        "responses": response_all
    }


def __commit_image_file(
        data: bytes,
        mode: str,
        auto_remove: bool,
        image_format: str,
        # WebP options
        method: int,
        lossless: bool,
        quality: int,

):
    """
    Commit single file to weed FS filer
    :param data:
    :param mode:
    :param auto_remove:
    :param image_format:
    :param method:
    :param lossless:
    :param quality:
    :return:
    """
    request_count.labels("__commit_image_file").inc()
    if mode not in {"keep", "block", "largest"}:
        raise ParameterError("mode should in keep/block/largest.")

    with BytesIO(data) as fp:
        im = Image.open(fp)
        image_format = image_format.upper()
        # Means don't need convert
        image_format_matched = image_format.lower() == "original" or im.format == image_format
        hash_id = get_hash(im)
        if not image_format_matched:
            # Won't convert animated image
            if hasattr(im, "is_animated") and im.is_animated:
                log.warning("Can't convert animated image format from {} -> {}".format(
                    im.format,
                    image_format
                ))
            else:
                with BytesIO() as wio:
                    if image_format == "WEBP":
                        im.save(
                            wio,
                            format="WEBP",
                            lossless=lossless,
                            method=method,
                            quality=quality
                        )
                    else:
                        im.save(wio, format=image_format)
                    wio.seek(0)
                    data = wio.read()
        # Get image hash by hash function

    lazy_file_list = LazyResource(lambda: filer_server.list_images(hash_id))
    with RedisDistributedLock(Redlock(
            redis_connection_pool
    ), hash_id) as _:
        if mode == "keep":
            need_to_write = True
        else:
            if len(lazy_file_list.resource) <= 0:
                need_to_write = True
            else:
                if mode == "block":
                    need_to_write = False
                elif mode == "largest":
                    # FIXME for now using file size to evaluate, using resolution is better!!!
                    # But before we're using MongoDB, it's hard to do this operation
                    max_file_size = max(
                        sum(chuck["size"] for chuck in info["chunks"]) for info in lazy_file_list.resource
                    )
                    need_to_write = len(data) > max_file_size
                else:
                    raise Exception("Unknown mode: {}".format(mode))
        if need_to_write:
            # File name parts:
            # <image hash>/<hostname>_<micro sec tick(%x)>_<random str>.img
            removed = []
            if auto_remove:
                for info in lazy_file_list.resource:
                    fn = info["FullPath"]
                    filer_server.delete_file(fn)
                    removed.append(fn)
            write_filename = "{}/{}_{:x}_{}.img".format(
                hash_id,
                socket.gethostname(),
                int(time.time() * 1_000_000),
                get_random_string(8)
            )
            filer_server.write_data(
                write_filename,
                data
            )

            return {
                "status": "success",
                "wrote": True,
                "filename": write_filename,
                "removed": removed,
                "hash": hash_id,
            }
        else:
            return {
                "status": "success",
                "wrote": False,
                "hash": hash_id,
            }

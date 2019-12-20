import json
import logging
import time
from io import BytesIO
import random
from urllib.parse import urljoin, urlencode
import numpy
import requests
from PIL import Image
from imagehash import average_hash

log = logging.getLogger(__file__)

logging.basicConfig(level=logging.INFO)

service_path = "http://nemivir:8000/"
filer_path = "http://filer:9401/"


def compare_difference(im1: Image, im2: Image, hash_size: int = 8):
    """
    Compare difference between image and loaded image
    :param im1:
    :param im2:
    :param hash_size:
    :return:
    """
    return average_hash(im1, hash_size=hash_size) - average_hash(im2, hash_size=hash_size)


def verify_image(filename: str):
    im = Image.open(filename)

    with open(filename, "rb") as fp:
        resp = requests.post(
            urljoin(service_path, "/upload"),
            data={
                "mode": "keep",
                "auto_remove": True
            },
            files={"file": fp},
        )
        resp.raise_for_status()
        write_response = resp.json()
        log.info("Raw image uploaded, response::\n{}".format(
            json.dumps(write_response, indent=2)
        ))
        image_hash = write_response["hash"]

    for rescale in [0.3, 0.6, None]:
        for image_format in ["PNG", "JPEG", "WEBP"]:
            params = {
                "image_format": image_format
            }
            if rescale is not None:
                params["rescale"] = rescale

            start_time = time.time()

            resp = requests.get(
                urljoin(service_path, "/hash/{}".format(image_hash)),
                params=urlencode(params)
            )
            resp.raise_for_status()
            response_data = resp.content
            log.info("Response got, size={} headers={}".format(
                len(response_data),
                json.dumps({
                    k: v for k, v in resp.headers.items()
                }, indent=2)
            ))
            passed_time = time.time() - start_time
            with BytesIO(response_data) as fp:
                im_load = Image.open(fp)
                difference = compare_difference(
                    im_load, im
                )
                report_detail = "scale={} format={} diff={} used={}ms".format(
                    rescale,
                    image_format,
                    difference,
                    passed_time * 1000
                )
                if difference > 6:
                    raise Exception("Failed while checking hash where: {}".format(report_detail))
                else:
                    log.info("Checked successfully: {}".format(report_detail))
    log.info("Removing file(s)...")
    requests.delete(urljoin(service_path, "/hash/{}".format(image_hash))).raise_for_status()


def clean_up():
    log.info("Cleaning up")
    hashes = [
        info["FullPath"].strip("/") for info in requests.get(
            urljoin(service_path, "/list/hash")
        ).json()["hashes"]
    ]
    for image_hash in hashes:
        log.info("Removing {}".format(image_hash))
        requests.delete(urljoin(service_path, "/hash/{}".format(image_hash))).raise_for_status()


def create_random_image(size_x, size_y, depth: int = 3):
    f1 = (6.0 / size_x) * (random.random() + 3)
    f2 = (6.0 / size_y) * (random.random() + 3)
    p1 = 1
    p2 = 1
    zs = numpy.random.rand(depth)
    T = numpy.zeros(shape=(size_x, size_y, depth), dtype="uint8")
    for x in range(size_x):
        for y in range(size_y):
            for z in range(depth):
                value = (numpy.sin(numpy.cos(f1 * x) * p2 + p1) + numpy.cos(numpy.sin(f2 * y) * p1 + p2) + 2 + zs[
                    z]) / 5
                T[x, y, z] = int(max(min(value * 256.0, 255), 0))
    return Image.fromarray(T).convert("RGB")


if __name__ == '__main__':
    log.info("Waiting for service initialized.")
    time.sleep(5)
    clean_up()
    for size in range(50, 100, 200):
        create_random_image(size, size).save("/tmp/test.jpg")
        verify_image("/tmp/test.jpg")
    clean_up()

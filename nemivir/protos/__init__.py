"""
Build protobuf:
$ protoc -I protos --python_out=nemivir/protos protos/image_cache.proto
"""

from .image_cache_pb2 import ImageResponse


def create_image_response(data: bytes, media_type: str) -> ImageResponse:
    ir = ImageResponse()
    ir.content = data
    ir.media_type = media_type
    return ir

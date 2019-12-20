"""
Image operations:
- Resize
- Reformat webp->?
"""
from enum import Enum, unique

from PIL import Image
from imagehash import average_hash


@unique
class ImageFormat(Enum):
    """
    Enum all supported format
    """
    JPEG = "jpeg"
    GIF = "gif"
    PNG = "png"
    WEBP = "webp"


def get_hash(image: Image) -> str:
    """
    Generate a hash From Image
    :param image:
    :return:
    """
    return str(average_hash(image=image, hash_size=10))

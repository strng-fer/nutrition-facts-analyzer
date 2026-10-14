"""
Utility helper functions for image operations.
"""
from PIL import Image
import io
from typing import Tuple


def bytes_to_pil_image(image_bytes: bytes) -> Image.Image:
    """Convert raw bytes to PIL Image (RGB mode)."""
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def pil_image_to_bytes(image: Image.Image, format: str = "JPEG") -> bytes:
    """Convert PIL Image to bytes."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return buffer.read()


def get_image_dimensions(image: Image.Image) -> Tuple[int, int]:
    """Get (width, height) of a PIL Image."""
    return image.size

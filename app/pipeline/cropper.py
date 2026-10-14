"""
Step 2: Crop & Preprocess gambar area tabel nutrisi.

Pipeline preprocessing:
1. Crop gambar berdasarkan bounding box dari Roboflow
2. Convert ke grayscale
3. Upscale 2x untuk font kecil (mg, mcg, %)
4. Denoise untuk menghilangkan noise kemasan
5. Adaptive threshold untuk meningkatkan kontras teks
"""
from PIL import Image
import cv2
import numpy as np
from app.config import IMAGE_UPSCALE_FACTOR
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def crop_nutrition_area(
    image: Image.Image,
    bbox: Dict[str, Any],
    padding: int = 10,
) -> Image.Image:
    """
    Memotong area tabel nutrisi dari gambar berdasarkan bounding box.

    Roboflow mengembalikan koordinat center-based (x, y) + width + height.
    Fungsi ini mengkonversi ke corner-based (left, top, right, bottom)
    dan menambahkan padding untuk menghindari teks terpotong di tepi.

    Args:
        image: PIL Image object dari gambar asli.
        bbox: Dict {x, y, width, height} dari Roboflow detection result.
        padding: Pixel tambahan di setiap sisi crop area.

    Returns:
        PIL Image yang sudah di-crop pada area tabel nutrisi.
    """
    img_width, img_height = image.size

    # Konversi center-based → corner-based coordinates
    left = int(bbox["x"] - bbox["width"] / 2) - padding
    top = int(bbox["y"] - bbox["height"] / 2) - padding
    right = int(bbox["x"] + bbox["width"] / 2) + padding
    bottom = int(bbox["y"] + bbox["height"] / 2) + padding

    # Clamp ke batas gambar agar tidak out-of-bounds
    left = max(0, left)
    top = max(0, top)
    right = min(img_width, right)
    bottom = min(img_height, bottom)

    cropped = image.crop((left, top, right, bottom))

    logger.info(
        f"Cropped nutrition area: "
        f"({left}, {top}, {right}, {bottom}) "
        f"from {img_width}x{img_height} image → "
        f"{cropped.size[0]}x{cropped.size[1]} crop"
    )

    return cropped


def preprocess_for_ocr(image: Image.Image) -> np.ndarray:
    """
    Preprocessing gambar cropped untuk meningkatkan akurasi OCR.

    Pipeline:
    1. Convert ke grayscale
    2. Upscale resolusi (2x default) untuk meningkatkan pembacaan font kecil
    3. Denoise untuk menghilangkan noise dari kemasan
    4. Adaptive thresholding untuk meningkatkan kontras teks vs background

    Args:
        image: PIL Image yang sudah di-crop pada area tabel nutrisi.

    Returns:
        numpy ndarray (OpenCV format, uint8) yang siap untuk OCR engine.
    """
    # PIL → OpenCV (numpy array, RGB → BGR not needed for grayscale)
    img_cv = np.array(image)

    # Step 1: Convert ke grayscale
    if len(img_cv.shape) == 3:
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_cv

    original_h, original_w = gray.shape

    # Step 2: Upscale — font kecil (6-8pt) jadi lebih terbaca oleh OCR
    upscaled = cv2.resize(
        gray,
        (original_w * IMAGE_UPSCALE_FACTOR, original_h * IMAGE_UPSCALE_FACTOR),
        interpolation=cv2.INTER_CUBIC,
    )

    # Step 3: Denoise — hilangkan noise dari glossy/textured packaging
    denoised = cv2.fastNlMeansDenoising(upscaled, h=10)

    # Step 4: Adaptive threshold — lebih baik dari Otsu untuk label berwarna
    # karena menangani variasi pencahayaan lokal pada kemasan
    thresh = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15,
        C=8,
    )

    logger.info(
        f"Preprocessing complete: "
        f"{original_w}x{original_h} → "
        f"{original_w * IMAGE_UPSCALE_FACTOR}x{original_h * IMAGE_UPSCALE_FACTOR} "
        f"(grayscale → denoise → adaptive threshold)"
    )

    return thresh

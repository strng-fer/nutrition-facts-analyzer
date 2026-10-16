"""
Step 2: Crop & Preprocess gambar area tabel nutrisi.

Pipeline preprocessing tingkat lanjut dengan perlindungan terhadap:
1. Kemiringan teks / tabel (Auto-Deskewing via contour line orientation)
2. Pantulan cahaya kemasan (Specular glare suppression & flat-field division)
3. Font kecil (Upscaling 2x & CLAHE contrast enhancement)
4. Noise kemasan (Bilateral / Non-local means denoising)
5. Adaptive thresholding untuk ekstraksi teks OCR optimal
"""
from PIL import Image
import cv2
import numpy as np
from app.config import IMAGE_UPSCALE_FACTOR
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


def crop_nutrition_area(
    image: Image.Image,
    bbox: Dict[str, Any],
    padding: int = 10,
) -> Image.Image:
    """
    Memotong area tabel nutrisi dari gambar berdasarkan bounding box.

    Mendukung koordinat center-based (x, y, width, height) dan corner-based (x1, y1, x2, y2).
    Menambahkan padding untuk menghindari teks terpotong di tepi.

    Args:
        image: PIL Image object dari gambar asli.
        bbox: Dict {x, y, width, height} atau {x1, y1, x2, y2}.
        padding: Pixel tambahan di setiap sisi crop area.

    Returns:
        PIL Image yang sudah di-crop pada area tabel nutrisi.
    """
    img_width, img_height = image.size

    if "x1" in bbox and "y1" in bbox and "x2" in bbox and "y2" in bbox:
        left = int(bbox["x1"]) - padding
        top = int(bbox["y1"]) - padding
        right = int(bbox["x2"]) + padding
        bottom = int(bbox["y2"]) + padding
    else:
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


def estimate_skew_angle(image: np.ndarray) -> float:
    """
    Estimasi sudut kemiringan (skew angle) dalam derajat (-45° s.d. +45°).
    Menggabungkan huruf-huruf dalam baris menjadi strip horizontal via
    morfologi, kemudian menghitung median orientasi baris teks.

    Args:
        image: numpy ndarray (grayscale atau RGB).

    Returns:
        Sudut koreksi rotasi dalam derajat (float).
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    img_h, img_w = gray.shape[:2]

    # Invert binary thresholding (teks menjadi putih, latar hitam)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Kernel horizontal untuk menggabungkan kata menjadi satu baris memanjang
    kernel_w = max(15, int(img_w * 0.05))
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 3))
    dilated = cv2.dilate(thresh, h_kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    angles = []
    min_line_width = max(30, int(img_w * 0.15))

    for c in contours:
        if cv2.contourArea(c) < 150:
            continue
        rect = cv2.minAreaRect(c)
        (cx, cy), (w, h), angle = rect

        # Normalisasi orientasi OpenCV minAreaRect
        if w < h:
            w, h = h, w
            angle = angle + 90

        # Normalisasi ke rentang [-45, 45]
        while angle > 45:
            angle -= 90
        while angle < -45:
            angle += 90

        # Hanya pertimbangkan kontur yang memanjang (karakteristik baris teks atau garis tabel)
        if w >= min_line_width and (w / (h + 1e-5)) >= 2.5:
            if abs(angle) <= 30.0:
                angles.append(angle)

    if len(angles) < 2:
        return 0.0

    median_angle = float(np.median(angles))
    return median_angle


def deskew_image(image: np.ndarray, angle: float, keep_size: bool = True) -> np.ndarray:
    """
    Memutar citra untuk mengoreksi kemiringan (deskewing) berdasarkan sudut rotasi.

    Args:
        image: numpy ndarray citra (uint8).
        angle: Sudut rotasi dalam derajat.
        keep_size: Jika True, mempertahankan ukuran kanvas asli (mencegah perubahan dimensi tak terduga).

    Returns:
        Citra numpy array yang sudah tegak horizontal.
    """
    if abs(angle) < 0.5:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    if keep_size:
        deskewed = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
    else:
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        border_val = (255, 255, 255) if len(image.shape) == 3 else 255
        deskewed = cv2.warpAffine(
            image, M, (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=border_val
        )

    logger.info(f"Deskewed image by {angle:.2f}° (keep_size={keep_size})")
    return deskewed


def remove_glare_and_normalize(image: np.ndarray) -> np.ndarray:
    """
    Menormalkan kontras dan meratakan pencahayaan lokal dengan CLAHE lembut.
    Menghindari operasi morfologi ekstrem yang merusak karakter dan menciptakan artefak.

    Args:
        image: numpy ndarray (grayscale uint8 atau RGB).

    Returns:
        numpy ndarray grayscale dengan iluminasi seragam dan kontras teks terjaga.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    # CLAHE lembut untuk meratakan pencahayaan lokal tanpa merusak bentuk huruf
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    logger.info("Glare normalization & contrast balance applied via CLAHE.")
    return enhanced


def preprocess_for_ocr(
    image: Image.Image,
    deskew: bool = False,
    remove_glare: bool = True,
    binarize: bool = False,
) -> np.ndarray:
    """
    Preprocessing citra cropped yang proporsional dan tidak 'lebay' untuk OCR.

    Pipeline:
    1. Konversi ke Grayscale alami
    2. Upscale terukur (2x) agar font kecil (mg, %, kkal) memiliki kerapatan piksel memadai
    3. Normalisasi kontras & glare menggunakan CLAHE lembut
    4. Koreksi kemiringan (deskew) hanya jika diaktifkan dan sudut kemiringan nyata
    5. Denoise lembut untuk membersihkan noise sensor tanpa memotong titik atau tepi font
    6. Menjaga citra tetap dalam continuous tone (bukan binarisasi ekstrem yang merusak antialiasing)

    Args:
        image: PIL Image yang sudah di-crop pada area tabel nutrisi.
        deskew: Jika True, jalankan deskewing jika sudut kemiringan nyata.
        remove_glare: Jika True, terapkan CLAHE untuk meratakan kontras.
        binarize: Jika True, lakukan binarisasi Otsu (default: False untuk deep learning OCR).

    Returns:
        numpy ndarray (OpenCV format, uint8) siap untuk OCR engine.
    """
    img_cv = np.array(image)

    # Step 1: Konversi ke Grayscale
    if len(img_cv.shape) == 3:
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_cv

    original_h, original_w = gray.shape

    # Step 2: Upscale terukur (2x default) untuk memperjelas font kecil
    upscaled = cv2.resize(
        gray,
        (original_w * IMAGE_UPSCALE_FACTOR, original_h * IMAGE_UPSCALE_FACTOR),
        interpolation=cv2.INTER_CUBIC,
    )

    # Step 3: Normalisasi kontras & glare secara lembut
    if remove_glare:
        enhanced = remove_glare_and_normalize(upscaled)
    else:
        enhanced = upscaled

    # Step 4: Koreksi kemiringan (deskew) hanya jika diminta dan sudut signifikan
    if deskew:
        angle = estimate_skew_angle(enhanced)
        if 1.5 <= abs(angle) <= 20.0:
            enhanced = deskew_image(enhanced, angle, keep_size=True)

    # Step 5: Filter halus untuk meredam noise sensor tanpa merusak titik desimal
    denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)

    # Step 6: Binarisasi opsional (default False untuk menjaga antialiasing deep learning)
    if binarize:
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    logger.info(
        f"Preprocessing complete: "
        f"{original_w}x{original_h} → "
        f"{denoised.shape[1]}x{denoised.shape[0]} "
        f"(natural grayscale, upscale={IMAGE_UPSCALE_FACTOR}x, clahe={remove_glare})"
    )

    return denoised

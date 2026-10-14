"""
Step 3: OCR — Ekstraksi teks dari gambar tabel nutrisi.

Strategi dual-engine:
1. PaddleOCR sebagai engine primer (superior untuk tabel/grid)
2. EasyOCR sebagai fallback jika PaddleOCR confidence rendah

Kedua engine di-lazy-load sebagai singleton untuk menghindari
overhead re-initialization pada setiap request.
"""
from paddleocr import PaddleOCR
import easyocr
import numpy as np
from app.config import OCR_CONFIDENCE_THRESHOLD
from typing import Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)

# ─── Lazy-loaded singletons ───
_paddle_ocr: Optional[PaddleOCR] = None
_easy_ocr: Optional[easyocr.Reader] = None


def _get_paddle_ocr() -> Optional[PaddleOCR]:
    """Lazy-load PaddleOCR instance (singleton pattern)."""
    global _paddle_ocr
    if _paddle_ocr is None:
        try:
            logger.info("Initializing PaddleOCR engine (first call)...")
            _paddle_ocr = PaddleOCR(lang="id")
        except Exception as e:
            logger.warning(f"PaddleOCR initialization failed: {e}")
            _paddle_ocr = None
    return _paddle_ocr


def _get_easy_ocr() -> Optional[easyocr.Reader]:
    """Lazy-load EasyOCR instance (singleton pattern)."""
    global _easy_ocr
    if _easy_ocr is None:
        try:
            logger.info("Initializing EasyOCR engine (first call)...")
            _easy_ocr = easyocr.Reader(
                ["id", "en"],   # Indonesia + English untuk produk impor
                gpu=False,       # CPU mode — ubah ke True jika ada GPU
                verbose=False,
            )
        except Exception as e:
            logger.error(f"EasyOCR initialization failed: {e}")
            _easy_ocr = None
    return _easy_ocr


def extract_text_paddleocr(image: np.ndarray) -> Tuple[str, float]:
    """
    Ekstrak teks menggunakan PaddleOCR.

    Args:
        image: numpy array (preprocessed image) dari cropper module.

    Returns:
        Tuple of (raw_text: str, avg_confidence: float).
        raw_text berisi semua baris teks yang diekstrak, dipisahkan newline.
        avg_confidence adalah rata-rata confidence score dari semua baris.
    """
    try:
        ocr = _get_paddle_ocr()
        if ocr is None:
            return "", 0.0

        results = ocr.ocr(image)

        if not results or not results[0]:
            logger.warning("PaddleOCR returned no results.")
            return "", 0.0

        lines: List[str] = []
        confidences: List[float] = []

        for item in results[0]:
            if isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[1], (list, tuple)):
                text = str(item[1][0])
                conf = float(item[1][1])
            elif isinstance(item, dict):
                text = str(item.get("rec_text", item.get("text", "")))
                conf = float(item.get("rec_score", item.get("score", 0.0)))
            else:
                continue

            if text.strip():
                lines.append(text)
                confidences.append(conf)

        raw_text = "\n".join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        logger.info(
            f"PaddleOCR: extracted {len(lines)} lines, "
            f"avg confidence: {avg_confidence:.3f}"
        )

        return raw_text, avg_confidence
    except Exception as e:
        logger.warning(f"PaddleOCR execution failed: {e}. Falling back to EasyOCR.")
        return "", 0.0


def extract_text_easyocr(image: np.ndarray) -> Tuple[str, float]:
    """
    Ekstrak teks menggunakan EasyOCR (fallback engine).

    Args:
        image: numpy array (preprocessed image) dari cropper module.

    Returns:
        Tuple of (raw_text: str, avg_confidence: float).
    """
    try:
        reader = _get_easy_ocr()
        if reader is None:
            return "", 0.0

        results = reader.readtext(image)

        if not results:
            logger.warning("EasyOCR returned no results.")
            return "", 0.0

        lines: List[str] = []
        confidences: List[float] = []

        for item in results:
            if len(item) >= 3:
                lines.append(str(item[1]))
                confidences.append(float(item[2]))

        raw_text = "\n".join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        logger.info(
            f"EasyOCR: extracted {len(lines)} lines, "
            f"avg confidence: {avg_confidence:.3f}"
        )

        return raw_text, avg_confidence
    except Exception as e:
        logger.error(f"EasyOCR execution failed: {e}")
        return "", 0.0


def extract_text(image: np.ndarray) -> Tuple[str, float, str]:
    """
    Pipeline OCR utama dengan strategi dual-engine fallback.

    Strategy:
    1. Coba PaddleOCR terlebih dahulu (superior untuk tabel)
    2. Jika avg confidence < threshold, fallback ke EasyOCR
    3. Kembalikan hasil engine dengan confidence terbaik

    Args:
        image: numpy array (preprocessed image) dari cropper module.

    Returns:
        Tuple of (raw_text, avg_confidence, engine_used).
        engine_used: "PaddleOCR" atau "EasyOCR".
    """
    # ── Primer: PaddleOCR ──
    paddle_text, paddle_conf = extract_text_paddleocr(image)

    if paddle_conf >= OCR_CONFIDENCE_THRESHOLD and paddle_text.strip():
        logger.info(
            f"PaddleOCR accepted (confidence {paddle_conf:.3f} ≥ "
            f"threshold {OCR_CONFIDENCE_THRESHOLD})"
        )
        return paddle_text, paddle_conf, "PaddleOCR"

    # ── Fallback: EasyOCR ──
    logger.warning(
        f"PaddleOCR confidence ({paddle_conf:.3f}) below threshold "
        f"({OCR_CONFIDENCE_THRESHOLD}) or text empty. "
        f"Falling back to EasyOCR."
    )

    easy_text, easy_conf = extract_text_easyocr(image)

    # Kembalikan engine dengan confidence terbaik
    if easy_conf > paddle_conf and easy_text.strip():
        logger.info(f"EasyOCR selected (confidence {easy_conf:.3f} > PaddleOCR {paddle_conf:.3f})")
        return easy_text, easy_conf, "EasyOCR"
    elif paddle_text.strip():
        logger.info(f"PaddleOCR retained despite low confidence ({paddle_conf:.3f})")
        return paddle_text, paddle_conf, "PaddleOCR"
    else:
        logger.warning("Both OCR engines produced poor results.")
        return easy_text, easy_conf, "EasyOCR"

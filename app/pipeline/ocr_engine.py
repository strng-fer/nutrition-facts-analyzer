"""
Step 3: OCR — Ekstraksi teks dari gambar tabel nutrisi.

Strategi dual-engine:
1. PaddleOCR sebagai engine primer (superior untuk tabel/grid)
2. EasyOCR sebagai fallback jika PaddleOCR confidence rendah

Kedua engine di-lazy-load sebagai singleton untuk menghindari
overhead re-initialization pada setiap request.

Juga menyediakan visualisasi bounding box teks OCR (draw_ocr_boxes)
untuk ditampilkan pada tab antarmuka pengguna.
"""
import re
from paddleocr import PaddleOCR
import easyocr
import cv2
import numpy as np
from PIL import Image
from app.config import OCR_CONFIDENCE_THRESHOLD
from typing import Tuple, List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# ─── Lazy-loaded singletons ───
_paddle_ocr: Optional[PaddleOCR] = None
_paddle_available: Optional[bool] = None
_easy_ocr: Optional[easyocr.Reader] = None


def _get_paddle_ocr() -> Optional[PaddleOCR]:
    """Lazy-load PaddleOCR instance (singleton pattern with failure detection)."""
    global _paddle_ocr, _paddle_available
    if _paddle_available is False:
        return None

    if _paddle_ocr is None:
        try:
            logger.info("Initializing PaddleOCR engine (lang='id')...")
            _paddle_ocr = PaddleOCR(lang="id")
            _paddle_available = True
        except Exception as e:
            logger.warning(f"PaddleOCR is not available ({e}). Using EasyOCR as primary.")
            _paddle_available = False
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


def clean_ocr_text(text: str) -> str:
    """
    Normalisasi teks hasil OCR untuk memperbaiki artefak umum pada label nutrisi:
    1. Mengganti Turkish dotless 'ı' menjadi 'i' dan 'İ' menjadi 'I'.
    2. Mengoreksi misread tanda '%' yang sering terbaca '%6' atau '96'.
    3. Mengoreksi satuan 'g' (gram) yang misread sebagai angka '9' di akhir bilangan.
    """
    # 1. Unicode normalisasi
    text = text.replace('\u0131', 'i').replace('\u0130', 'I')
    # 2. Perbaiki artefak tanda persen yang sering terbaca sebagai 86/96/%6 (cth: '686' -> '6%', '796' -> '7%', '5%6' -> '5%')
    text = re.sub(r'\b(\d{1,2})(?:86|96|%6)\b', r'\1%', text)
    text = re.sub(r'(\d+)\s*%\s*6\b', r'\1%', text)
    # 3. Perbaiki 'g' yang terbaca '9' tepat setelah angka (cth: '309' -> '30 g', '59' -> '5 g')
    text = re.sub(r'(?<=\d)9\b', ' g', text)
    return text.strip()


def reconstruct_table_lines(
    ocr_raw_items: List[Tuple[Any, str, float]],
) -> Tuple[str, float, List[Dict[str, Any]]]:
    """
    Mengelompokkan dan merekonstruksi potongan bounding box EasyOCR
    menjadi baris-baris tabel yang teratur dari atas ke bawah, kiri ke kanan.

    Mencegah hasil OCR yang acak/terbalik urutannya akibat traversal graf detektor.
    """
    if not ocr_raw_items:
        return "", 0.0, []

    parsed_items = []
    for item in ocr_raw_items:
        if len(item) < 3:
            continue
        box = item[0]
        raw_text = str(item[1]).strip()
        conf = float(item[2])

        clean_t = clean_ocr_text(raw_text)
        if not clean_t:
            continue

        try:
            pts = [[int(p[0]), int(p[1])] for p in box]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            ymin, ymax = min(ys), max(ys)
            xmin, xmax = min(xs), max(xs)
        except Exception:
            continue

        parsed_items.append({
            "text": clean_t,
            "confidence": conf,
            "box": pts,
            "ymin": ymin,
            "ymax": ymax,
            "xmin": xmin,
            "xmax": xmax,
            "y_center": (ymin + ymax) / 2.0,
            "h": max(1.0, ymax - ymin),
        })

    if not parsed_items:
        return "", 0.0, []

    # 1. Urutkan berdasarkan koordinat vertikal (y_center)
    parsed_items.sort(key=lambda it: it["y_center"])

    # 2. Klasterisasi baris horizontal
    lines: List[List[Dict[str, Any]]] = []
    for it in parsed_items:
        placed = False
        for line in lines:
            line_y_avg = sum(m["y_center"] for m in line) / len(line)
            line_h_avg = sum(m["h"] for m in line) / len(line)
            # Toleransi tinggi baris (vertikal overlap)
            if abs(it["y_center"] - line_y_avg) <= max(line_h_avg, it["h"]) * 0.65:
                line.append(it)
                placed = True
                break
        if not placed:
            lines.append([it])

    # 3. Urutkan baris dari atas ke bawah
    lines.sort(key=lambda line: min(m["ymin"] for m in line))

    reconstructed_lines: List[str] = []
    final_ocr_items: List[Dict[str, Any]] = []
    all_confidences: List[float] = []

    for line in lines:
        # Urutkan item dalam satu baris dari kiri ke kanan (nama nutrisi -> nilai -> AKG%)
        line.sort(key=lambda m: m["xmin"])
        line_text = "  ".join(m["text"] for m in line)
        line_conf = sum(m["confidence"] for m in line) / len(line)
        all_confidences.extend(m["confidence"] for m in line)

        # Hitung bounding box keseluruhan untuk satu baris
        l_xmin = min(m["xmin"] for m in line)
        l_ymin = min(m["ymin"] for m in line)
        l_xmax = max(m["xmax"] for m in line)
        l_ymax = max(m["ymax"] for m in line)
        line_box = [[l_xmin, l_ymin], [l_xmax, l_ymin], [l_xmax, l_ymax], [l_xmin, l_ymax]]

        reconstructed_lines.append(line_text)
        final_ocr_items.append({
            "text": line_text,
            "confidence": round(line_conf, 3),
            "box": line_box,
        })

    raw_text = "\n".join(reconstructed_lines)
    avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    return raw_text, round(avg_conf, 3), final_ocr_items


def draw_ocr_boxes(
    base_image: Image.Image,
    ocr_items: List[Dict[str, Any]],
) -> Image.Image:
    """
    Menggambar kotak bounding box semi-transparan pada setiap baris teks
    yang berhasil dideteksi oleh OCR engine untuk visualisasi di Web UI.

    Args:
        base_image: PIL Image area tabel nutrisi (cropped).
        ocr_items: List dict [{"text": ..., "confidence": ..., "box": ...}].

    Returns:
        PIL Image dengan highlight visual bounding box per baris teks.
    """
    img_cv = np.array(base_image.convert("RGB"))
    overlay = img_cv.copy()

    for item in ocr_items:
        box = item.get("box")
        if not box:
            continue
        try:
            pts = np.array(box, dtype=np.int32).reshape((-1, 1, 2))
            # Highlight hijau zamrud semi-transparan
            cv2.fillPoly(overlay, [pts], (16, 185, 129))
            cv2.polylines(img_cv, [pts], isClosed=True, color=(52, 211, 153), thickness=2)
        except Exception:
            continue

    # Blend 22% overlay + 78% citra asli
    cv2.addWeighted(overlay, 0.22, img_cv, 0.78, 0, img_cv)
    return Image.fromarray(img_cv)


def extract_text_paddleocr(
    image: np.ndarray,
) -> Tuple[str, float, List[Dict[str, Any]]]:
    """
    Ekstrak teks menggunakan PaddleOCR.

    Mendukung format return PaddleOCR 2.x ([[[box], (text, score)]])
    dan format PaddleX 3.x ({'rec_text': [...], 'rec_score': [...], 'dt_polys': [...]}).

    Args:
        image: numpy array (preprocessed image).

    Returns:
        Tuple of (raw_text: str, avg_confidence: float, ocr_items: List[dict]).
    """
    try:
        ocr = _get_paddle_ocr()
        if ocr is None:
            return "", 0.0, []

        results = ocr.ocr(image)

        if not results or not results[0]:
            logger.warning("PaddleOCR returned no results.")
            return "", 0.0, []

        lines: List[str] = []
        confidences: List[float] = []
        ocr_items: List[Dict[str, Any]] = []

        res_first = results[0]

        # Format PaddleX 3.x
        if isinstance(res_first, dict):
            rec_texts = res_first.get("rec_text", [])
            rec_scores = res_first.get("rec_score", [])
            dt_polys = res_first.get("dt_polys", [])
            for idx, text_val in enumerate(rec_texts):
                t = str(text_val).strip()
                s = float(rec_scores[idx]) if idx < len(rec_scores) else 0.0
                b = dt_polys[idx] if idx < len(dt_polys) else None
                if t:
                    lines.append(t)
                    confidences.append(s)
                    ocr_items.append({"text": t, "confidence": round(s, 3), "box": b})

        # Format PaddleOCR 2.x
        elif isinstance(res_first, (list, tuple)):
            for item in res_first:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    box = item[0]
                    text_data = item[1]
                    if isinstance(text_data, (list, tuple)) and len(text_data) >= 2:
                        t = str(text_data[0]).strip()
                        s = float(text_data[1])
                        if t:
                            lines.append(t)
                            confidences.append(s)
                            ocr_items.append({"text": t, "confidence": round(s, 3), "box": box})

        raw_text = "\n".join(lines)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        logger.info(
            f"PaddleOCR: extracted {len(lines)} lines, "
            f"avg confidence: {avg_confidence:.3f}"
        )

        return raw_text, avg_confidence, ocr_items

    except Exception as e:
        logger.warning(f"PaddleOCR execution failed: {e}. Falling back to EasyOCR.")
        return "", 0.0, []


def extract_text_easyocr(
    image: np.ndarray,
) -> Tuple[str, float, List[Dict[str, Any]]]:
    """
    Ekstrak teks menggunakan EasyOCR dengan parameter natural dan rekonstruksi baris tabel.

    Tidak menggunakan parameter ekstrem/aneh yang merusak pembacaan font nutrisi.
    Hasil bounding box disusun secara horizontal per baris dan diurutkan dari atas ke bawah.

    Args:
        image: numpy array (preprocessed image).

    Returns:
        Tuple of (raw_text: str, avg_confidence: float, ocr_items: List[dict]).
    """
    try:
        reader = _get_easy_ocr()
        if reader is None:
            return "", 0.0, []

        # Parameter natural & standar EasyOCR (tanpa parameter aneh yang merusak font)
        results = reader.readtext(image, detail=1, min_size=10)

        if not results:
            logger.warning("EasyOCR returned no results.")
            return "", 0.0, []

        raw_text, avg_confidence, ocr_items = reconstruct_table_lines(results)

        logger.info(
            f"EasyOCR: extracted {len(ocr_items)} reconstructed table lines, "
            f"avg confidence: {avg_confidence:.3f}"
        )

        return raw_text, avg_confidence, ocr_items

    except Exception as e:
        logger.error(f"EasyOCR execution failed: {e}")
        return "", 0.0, []


def extract_text(
    image: np.ndarray,
    raw_crop_image: Optional[Image.Image] = None,
) -> Tuple[str, float, str, Optional[Image.Image], List[Dict[str, Any]]]:
    """
    Pipeline OCR utama dengan strategi dual-engine fallback dan visualisasi teks.

    Strategy:
    1. Periksa ketersediaan PaddleOCR; jika tersedia dan confidence memadai, gunakan.
    2. Jika PaddleOCR tidak tersedia (cth: ketidakcocokan NumPy 2.x) atau confidence rendah,
       langsung jalankan EasyOCR sebagai primary engine yang stabil dan akurat.
    3. Rekonstruksi baris-baris tabel nutrisi dari atas ke bawah.
    4. Buat visualisasi gambar teranotasi kotak teks OCR (ocr_annotated_image).

    Args:
        image: numpy array (preprocessed image) dari cropper module.
        raw_crop_image: PIL Image asli cropped untuk canvas gambar teranotasi OCR.

    Returns:
        Tuple of (raw_text, avg_confidence, engine_used, ocr_annotated_image, ocr_items).
    """
    paddle_ocr_inst = _get_paddle_ocr()

    if paddle_ocr_inst is not None:
        paddle_text, paddle_conf, paddle_items = extract_text_paddleocr(image)

        if paddle_conf >= OCR_CONFIDENCE_THRESHOLD and paddle_text.strip():
            best_text = paddle_text
            best_conf = paddle_conf
            best_engine = "PaddleOCR"
            best_items = paddle_items
        else:
            easy_text, easy_conf, easy_items = extract_text_easyocr(image)
            if easy_conf >= paddle_conf and easy_text.strip():
                best_text = easy_text
                best_conf = easy_conf
                best_engine = "EasyOCR"
                best_items = easy_items
            elif paddle_text.strip():
                best_text = paddle_text
                best_conf = paddle_conf
                best_engine = "PaddleOCR"
                best_items = paddle_items
            else:
                best_text = easy_text
                best_conf = easy_conf
                best_engine = "EasyOCR"
                best_items = easy_items
    else:
        # EasyOCR langsung sebagai primary engine tanpa overhead/delay
        easy_text, easy_conf, easy_items = extract_text_easyocr(image)
        best_text = easy_text
        best_conf = easy_conf
        best_engine = "EasyOCR"
        best_items = easy_items

    # ── Buat visualisasi bounding box per baris teks OCR ──
    ocr_annotated_pil: Optional[Image.Image] = None
    if raw_crop_image is not None and best_items:
        try:
            ocr_annotated_pil = draw_ocr_boxes(raw_crop_image, best_items)
        except Exception as err:
            logger.warning(f"Failed to draw OCR boxes: {err}")
            ocr_annotated_pil = raw_crop_image
    elif best_items:
        try:
            base_pil = Image.fromarray(image if len(image.shape) == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2RGB))
            ocr_annotated_pil = draw_ocr_boxes(base_pil, best_items)
        except Exception:
            pass

    return best_text, best_conf, best_engine, ocr_annotated_pil, best_items

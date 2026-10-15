"""
FastAPI Backend — Nutrition Facts Extraction API.

Main pipeline endpoint: POST /extract-nutrition
Accepts an image upload and returns structured NutritionFacts JSON.

Pipeline: Detection (YOLOv8) → Crop & Preprocess (OpenCV) → OCR (PaddleOCR) → LLM (Gemini) → Validated JSON
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from PIL import Image
from pathlib import Path
import io
import base64
import logging

from app.schemas import ExtractionResult
from app.pipeline.detector import detect_nutrition_table
from app.pipeline.cropper import crop_nutrition_area, preprocess_for_ocr
from app.pipeline.ocr_engine import extract_text
from app.pipeline.llm_extractor import reconstruct_nutrition_data

# ─── Directories ───
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# ─── Logging ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ─── FastAPI App ───
app = FastAPI(
    title="🍎 Nutrition Facts Extractor API",
    description=(
        "Ekstrak informasi nilai gizi dari gambar kemasan produk.\n\n"
        "Pipeline: Detection (YOLOv8 Kustom) → Crop (OpenCV) → OCR (PaddleOCR) → "
        "LLM Reconstruction (Gemini)"
    ),
    version="1.1.0",
)

# CORS — izinkan semua origin untuk development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Supported image MIME types
SUPPORTED_FORMATS = {"image/jpeg", "image/png", "image/webp"}


def image_to_base64_data_url(image: Image.Image, max_dim: int = 1200, quality: int = 85) -> str:
    """Konversi PIL Image ke base64 data URL untuk ditransfer ke antarmuka web."""
    img = image.copy()
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the interactive single-page Web UI."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Index template not found")
    return FileResponse(index_file)


@app.post("/extract-nutrition", response_model=ExtractionResult)
async def extract_nutrition(file: UploadFile = File(...)):
    """
    Pipeline utama untuk mengekstrak Nutrition Facts dari gambar kemasan.

    **Input:** Gambar kemasan produk (JPEG/PNG/WebP) via multipart upload.

    **Output:** JSON terstruktur berisi data nutrisi yang sudah diparsing,
    visualisasi bounding box, crop tabel nutrisi, dan metadata pipeline.

    **Pipeline:**
    1. **Detection** — YOLOv8 (yolov8.pt kustom) mendeteksi lokasi tabel nutrisi
    2. **Crop** — Pillow memotong area tabel + OpenCV preprocessing
    3. **OCR** — PaddleOCR/EasyOCR mengekstrak teks dari gambar cropped
    4. **LLM** — Gemini merekonstruksi teks OCR menjadi JSON terstruktur
    """
    warnings: list[str] = []

    # ── Validasi format input ──
    if file.content_type not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Format gambar tidak didukung: {file.content_type}. "
                f"Gunakan JPEG, PNG, atau WebP."
            ),
        )

    try:
        # ── Baca image ──
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        logger.info(
            f"Received image: {file.filename} "
            f"({image.size[0]}x{image.size[1]}, {file.content_type})"
        )

        # ═══════════════════════════════════════
        # STEP 1: DETECTION (YOLOv8)
        # ═══════════════════════════════════════
        detection_result = detect_nutrition_table(image)

        detection_confidence = None
        detection_model = "YOLOv8"
        annotated_image_b64 = None
        cropped_image_b64 = None

        # ═══════════════════════════════════════
        # STEP 2: CROP & PREPROCESS
        # ═══════════════════════════════════════
        if detection_result:
            detection_confidence = detection_result.get("confidence")
            detection_model = detection_result.get("model", "YOLOv8")

            # Ambil visualisasi bounding box jika ada
            annotated_pil = detection_result.get("annotated_image")
            if annotated_pil:
                annotated_image_b64 = image_to_base64_data_url(annotated_pil)

            cropped_image = crop_nutrition_area(image, detection_result)
            cropped_image_b64 = image_to_base64_data_url(cropped_image)
            logger.info("✂️ Nutrition table detected by YOLOv8 and cropped.")
        else:
            # FALLBACK: Tidak ada deteksi → gunakan full image
            warnings.append(
                "Tabel nutrisi tidak terdeteksi oleh model YOLOv8. "
                "Menggunakan seluruh gambar untuk OCR (akurasi mungkin menurun)."
            )
            cropped_image = image
            cropped_image_b64 = image_to_base64_data_url(image)
            logger.warning("⚠️ No YOLOv8 detection — using full image for OCR.")

        preprocessed = preprocess_for_ocr(cropped_image)

        # ═══════════════════════════════════════
        # STEP 3: OCR
        # ═══════════════════════════════════════
        raw_text, ocr_confidence, engine_used = extract_text(preprocessed)

        if not raw_text.strip():
            return ExtractionResult(
                success=False,
                error=(
                    "OCR gagal mengekstrak teks dari gambar. "
                    "Kemungkinan penyebab: gambar terlalu buram, resolusi terlalu rendah, "
                    "atau gambar tidak mengandung teks tabel nutrisi. "
                    "Coba upload gambar dengan kualitas lebih tinggi."
                ),
                detection_confidence=(
                    round(detection_confidence, 3) if detection_confidence else None
                ),
                detection_model=detection_model,
                annotated_image=annotated_image_b64,
                cropped_image=cropped_image_b64,
                warnings=warnings,
            )

        if ocr_confidence < 0.4:
            warnings.append(
                f"Confidence OCR sangat rendah ({ocr_confidence:.1%}). "
                f"Hasil ekstraksi mungkin kurang akurat."
            )

        logger.info(f"📖 OCR completed: {engine_used} (confidence: {ocr_confidence:.3f})")

        # ═══════════════════════════════════════
        # STEP 4: LLM RECONSTRUCTION (Gemini)
        # ═══════════════════════════════════════
        nutrition_data = reconstruct_nutrition_data(raw_text)

        # Post-validation: cek apakah LLM menemukan data nutrisi
        if not nutrition_data.nutrients:
            warnings.append(
                "LLM tidak menemukan data nutrisi spesifik dalam teks OCR. "
                "Teks mungkin tidak mengandung informasi nilai gizi."
            )

        logger.info(
            f"✅ Pipeline complete — "
            f"{len(nutrition_data.nutrients)} nutrients extracted"
        )

        return ExtractionResult(
            success=True,
            nutrition_data=nutrition_data,
            raw_ocr_text=raw_text,
            ocr_engine_used=engine_used,
            ocr_confidence=round(ocr_confidence, 3),
            detection_confidence=(
                round(detection_confidence, 3) if detection_confidence else None
            ),
            detection_model=detection_model,
            annotated_image=annotated_image_b64,
            cropped_image=cropped_image_b64,
            warnings=warnings,
        )

    except ValueError as ve:
        logger.error(f"Pipeline ValueError: {ve}")
        return ExtractionResult(
            success=False,
            error=str(ve),
            warnings=warnings,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in pipeline: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@app.get("/health")
async def health_check():
    """Health check endpoint untuk monitoring."""
    return {
        "status": "healthy",
        "service": "nutrition-facts-extractor",
        "model": "YOLOv8",
        "version": "1.1.0",
    }

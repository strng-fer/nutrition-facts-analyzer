"""
Step 1: Nutrition Facts Table Detection via Custom YOLOv8 Model.

Menggunakan model YOLOv8 (yolov8.pt) hasil training mandiri untuk
mendeteksi lokasi bounding box tabel informasi nilai gizi pada gambar kemasan produk.

Mengembalikan bounding box coordinates (center-based dan corner-based)
serta citra teranotasi (annotated_image) dengan visualisasi bounding box untuk UI.
"""
from pathlib import Path
from typing import Optional, Dict, Any, Union
import logging
from PIL import Image

from app.config import (
    YOLO_MODEL_PATH,
    DETECTION_CONFIDENCE_THRESHOLD,
    ROBOFLOW_API_KEY,
    ROBOFLOW_MODEL_ID,
    ROBOFLOW_API_URL,
)

logger = logging.getLogger(__name__)

# Global cache singleton untuk YOLOv8 model
_yolo_model = None


def get_yolo_model():
    """
    Inisialisasi atau ambil instance singleton model YOLOv8.
    Memuat model sekali saja ke memori untuk performa inferensi yang optimal (<150ms).
    """
    global _yolo_model
    if _yolo_model is None:
        model_path = Path(YOLO_MODEL_PATH)
        if not model_path.exists():
            raise FileNotFoundError(
                f"File model YOLOv8 tidak ditemukan di: {model_path.resolve()}. "
                f"Pastikan file yolov8.pt tersedia di root repositori."
            )
        try:
            from ultralytics import YOLO
            logger.info(f"Loading custom YOLOv8 model from {model_path}...")
            _yolo_model = YOLO(str(model_path))
            logger.info(f"YOLOv8 loaded successfully. Detected classes: {_yolo_model.names}")
        except Exception as e:
            logger.error(f"Gagal memuat YOLOv8 model: {e}")
            raise
    return _yolo_model


def detect_nutrition_table(image: Union[Image.Image, str]) -> Optional[Dict[str, Any]]:
    """
    Mendeteksi bounding box tabel nutrisi dari citra kemasan menggunakan YOLOv8.

    Args:
        image: PIL Image object atau string path file gambar (JPG/PNG/WebP).

    Returns:
        Dict dengan keys:
            {
                "x": center_x,
                "y": center_y,
                "width": bbox_width,
                "height": bbox_height,
                "x1": left,
                "y1": top,
                "x2": right,
                "y2": bottom,
                "confidence": float,
                "class_name": str,
                "annotated_image": PIL.Image,  # Gambar dengan visualisasi bounding box
                "model": "YOLOv8",
            }
        None jika tidak ada deteksi yang memenuhi threshold.
    """
    # Pastikan citra berformat RGB PIL Image
    if isinstance(image, str):
        pil_image = Image.open(image).convert("RGB")
    elif isinstance(image, Image.Image):
        pil_image = image.convert("RGB")
    else:
        raise TypeError(f"Tipe citra tidak didukung: {type(image)}. Gunakan PIL.Image atau path str.")

    try:
        model = get_yolo_model()
        results = model.predict(
            source=pil_image,
            conf=DETECTION_CONFIDENCE_THRESHOLD,
            verbose=False,
        )

        if not results or len(results[0].boxes) == 0:
            logger.warning("No nutrition table detected by YOLOv8.")
            return None

        boxes = results[0].boxes
        # Pilih prediksi dengan confidence tertinggi
        best_idx = int(boxes.conf.argmax().item())
        best_box = boxes[best_idx]
        conf = float(best_box.conf.item())

        if conf < DETECTION_CONFIDENCE_THRESHOLD:
            logger.warning(
                f"YOLOv8 detection confidence ({conf:.2f}) below threshold "
                f"({DETECTION_CONFIDENCE_THRESHOLD}). Treating as no detection."
            )
            return None

        xywh = best_box.xywh[0].tolist()
        xyxy = best_box.xyxy[0].tolist()
        cls_id = int(best_box.cls.item())
        cls_name = model.names.get(cls_id, "nutrition table")

        # Visualisasi bounding box via ultralytics plot
        annotated_pil = results[0].plot(pil=True)

        logger.info(
            f"YOLOv8 detected '{cls_name}' - confidence: {conf:.2%}, "
            f"bbox: [x={xywh[0]:.1f}, y={xywh[1]:.1f}, w={xywh[2]:.1f}, h={xywh[3]:.1f}]"
        )

        return {
            "x": xywh[0],
            "y": xywh[1],
            "width": xywh[2],
            "height": xywh[3],
            "x1": xyxy[0],
            "y1": xyxy[1],
            "x2": xyxy[2],
            "y2": xyxy[3],
            "confidence": conf,
            "class_name": cls_name,
            "annotated_image": annotated_pil,
            "model": "YOLOv8",
        }

    except Exception as e:
        logger.error(f"YOLOv8 detection failed: {e}. Attempting Roboflow fallback if configured...")
        # Fallback ke Roboflow jika API key tersedia dan YOLO mengalami error tak terduga
        if ROBOFLOW_API_KEY:
            return _roboflow_fallback(pil_image)
        raise


def _roboflow_fallback(image: Image.Image) -> Optional[Dict[str, Any]]:
    """Fallback deteksi menggunakan Roboflow jika YOLOv8 mengalami error."""
    import tempfile
    import os
    from inference_sdk import InferenceHTTPClient

    try:
        client = InferenceHTTPClient(api_url=ROBOFLOW_API_URL, api_key=ROBOFLOW_API_KEY)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            image.save(tmp, format="JPEG")
            tmp_path = tmp.name

        try:
            result = client.infer(tmp_path, model_id=ROBOFLOW_MODEL_ID)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        predictions = result.get("predictions", [])
        if not predictions:
            return None

        best_prediction = max(predictions, key=lambda p: p["confidence"])
        if best_prediction["confidence"] < DETECTION_CONFIDENCE_THRESHOLD:
            return None

        return {
            "x": best_prediction["x"],
            "y": best_prediction["y"],
            "width": best_prediction["width"],
            "height": best_prediction["height"],
            "confidence": best_prediction["confidence"],
            "class_name": "nutrition table",
            "annotated_image": None,
            "model": "Roboflow",
        }
    except Exception as err:
        logger.error(f"Roboflow fallback also failed: {err}")
        return None

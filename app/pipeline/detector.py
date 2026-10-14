"""
Step 1: Nutrition Facts Table Detection via Roboflow.

Menggunakan model 'nutrition_label_information/1' dari Roboflow untuk
mendeteksi lokasi bounding box tabel informasi nilai gizi pada gambar kemasan.

Roboflow response format:
{
    "predictions": [
        {
            "x": 320,       # center x
            "y": 450,       # center y
            "width": 280,   # bbox width
            "height": 400,  # bbox height
            "confidence": 0.92,
            "class": "nutrition_table"
        }
    ]
}
"""
from inference_sdk import InferenceHTTPClient
from app.config import (
    ROBOFLOW_API_KEY,
    ROBOFLOW_MODEL_ID,
    ROBOFLOW_API_URL,
    DETECTION_CONFIDENCE_THRESHOLD,
)
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def init_roboflow_client() -> InferenceHTTPClient:
    """Inisialisasi Roboflow Inference HTTP client."""
    if not ROBOFLOW_API_KEY:
        raise ValueError(
            "ROBOFLOW_API_KEY is not set. "
            "Please set it in your .env file. "
            "Get your key at https://app.roboflow.com/settings/api-key"
        )
    client = InferenceHTTPClient(
        api_url=ROBOFLOW_API_URL,
        api_key=ROBOFLOW_API_KEY,
    )
    try:
        from inference_sdk import InferenceConfiguration
        client.configure(InferenceConfiguration(api_key_transport="both"))
    except Exception:
        pass
    return client


def detect_nutrition_table(image_path: str) -> Optional[Dict[str, Any]]:
    """
    Mendeteksi bounding box tabel nutrisi dari gambar.

    Args:
        image_path: Path absolut ke file gambar (JPG/PNG).

    Returns:
        Dict dengan keys {x, y, width, height, confidence} jika terdeteksi,
        None jika tidak ada deteksi yang memenuhi threshold.
    """
    client = init_roboflow_client()

    try:
        result = client.infer(image_path, model_id=ROBOFLOW_MODEL_ID)
        predictions = result.get("predictions", [])

        if not predictions:
            logger.warning("No nutrition table detected in image.")
            return None

        # Ambil prediksi dengan confidence tertinggi
        best_prediction = max(predictions, key=lambda p: p["confidence"])

        if best_prediction["confidence"] < DETECTION_CONFIDENCE_THRESHOLD:
            logger.warning(
                f"Detection confidence ({best_prediction['confidence']:.2f}) "
                f"below threshold ({DETECTION_CONFIDENCE_THRESHOLD}). "
                f"Treating as no detection."
            )
            return None

        logger.info(
            f"Detected nutrition table — "
            f"confidence: {best_prediction['confidence']:.2f}, "
            f"bbox: ({best_prediction['x']}, {best_prediction['y']}, "
            f"{best_prediction['width']}, {best_prediction['height']})"
        )

        return {
            "x": best_prediction["x"],
            "y": best_prediction["y"],
            "width": best_prediction["width"],
            "height": best_prediction["height"],
            "confidence": best_prediction["confidence"],
        }

    except Exception as e:
        logger.error(f"Roboflow detection failed: {e}")
        raise

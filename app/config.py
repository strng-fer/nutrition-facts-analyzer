"""
Application configuration — loads API keys and constants from environment.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Roboflow ───
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")
ROBOFLOW_MODEL_ID = "nutrition_label_information/1"
ROBOFLOW_API_URL = "https://serverless.roboflow.com"

# ─── Gemini ───
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# ─── OCR ───
OCR_CONFIDENCE_THRESHOLD = 0.6   # Minimum avg confidence before fallback to EasyOCR
IMAGE_UPSCALE_FACTOR = 2         # Upscale cropped image for better OCR accuracy

# ─── Detection (YOLOv8 & Roboflow Fallback) ───
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", str(BASE_DIR / "yolov8.pt"))
DETECTION_CONFIDENCE_THRESHOLD = float(os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.25"))

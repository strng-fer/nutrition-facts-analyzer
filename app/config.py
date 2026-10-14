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

# ─── Detection ───
DETECTION_CONFIDENCE_THRESHOLD = 0.3  # Minimum detection confidence to accept bbox

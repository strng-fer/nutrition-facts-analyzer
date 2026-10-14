# 🍎 Nutrition Facts Extractor

Aplikasi AI untuk mengekstrak informasi **Nutrition Facts / Informasi Nilai Gizi** dari gambar kemasan produk makanan/minuman.

## 🏗️ Pipeline

```
📷 Upload Gambar → 🔍 Detection (Roboflow) → ✂️ Crop (OpenCV) → 📖 OCR (PaddleOCR) → 🧠 LLM (Gemini) → 📊 JSON
```

| Step | Teknologi | Fungsi |
|:-----|:----------|:-------|
| Detection | Roboflow `inference-sdk` | Deteksi bounding box tabel nutrisi |
| Crop & Preprocess | Pillow + OpenCV | Potong area tabel + preprocessing (grayscale, upscale, threshold) |
| OCR | PaddleOCR (primer) + EasyOCR (fallback) | Ekstrak teks dari gambar |
| LLM Reconstruction | Google Gemini Flash | Perbaiki typo OCR + rekonstruksi ke JSON terstruktur |

## 📦 Quick Start

### 1. Clone & Setup
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
# Copy template
cp .env.example .env

# Edit .env dan isi API keys:
# ROBOFLOW_API_KEY=your_key   → https://app.roboflow.com/settings/api-key
# GEMINI_API_KEY=your_key     → https://aistudio.google.com/apikey
```

### 3. Run Application (Web UI + API)
```bash
uvicorn app.main:app --reload --port 8000
```
- **Web UI:** Buka `http://127.0.0.1:8000` di browser.
- **API Docs (Swagger):** Buka `http://127.0.0.1:8000/docs`.

*(Tidak memerlukan server frontend terpisah — FastAPI langsung melayani antarmuka web interaktif dan REST API).*

## 🧪 Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_cropper.py -v
```

## 📁 Project Structure
```
nutritionFacts/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app (Web UI: GET /, API: POST /extract-nutrition)
│   ├── config.py             # API keys & constants
│   ├── schemas.py            # Pydantic models (NutritionFacts, ExtractionResult)
│   ├── static/               # Frontend assets
│   │   ├── css/style.css     # Modern glassmorphism design system
│   │   └── js/app.js         # Drag-drop upload, pipeline animation, interactive table
│   ├── templates/
│   │   └── index.html        # Single-page Web UI template
│   ├── pipeline/
│   │   ├── detector.py       # Roboflow detection
│   │   ├── cropper.py        # Image crop + preprocessing
│   │   ├── ocr_engine.py     # PaddleOCR + EasyOCR dual-engine
│   │   └── llm_extractor.py  # Gemini few-shot prompting
│   └── utils/
│       └── image_utils.py    # Image format helpers
├── tests/
│   ├── test_cropper.py       # Cropper unit tests
│   └── test_schemas.py       # Schema validation tests
├── .env.example              # API key template
├── requirements.txt          # Python dependencies
└── README.md
```

## 🔑 API Endpoint

### `POST /extract-nutrition`
Upload gambar kemasan → terima JSON nutrisi terstruktur.

**Request:**
```bash
curl -X POST "http://127.0.0.1:8000/extract-nutrition" \
     -F "file=@nutrition_label.jpg"
```

**Response (success):**
```json
{
  "success": true,
  "nutrition_data": {
    "product_name": null,
    "serving_size": "1 bungkus (25g)",
    "servings_per_package": "1",
    "calories": "100 kkal",
    "nutrients": [
      {"name": "Lemak Total", "amount_per_serving": "5 g", "percent_daily_value": "7%"},
      {"name": "Protein", "amount_per_serving": "2 g", "percent_daily_value": "3%"}
    ]
  },
  "raw_ocr_text": "...",
  "ocr_engine_used": "PaddleOCR",
  "ocr_confidence": 0.847,
  "detection_confidence": 0.923,
  "warnings": []
}
```

## ⚠️ Error Handling

| Skenario | Respons Sistem |
|:---------|:---------------|
| Tabel nutrisi tidak terdeteksi | Fallback: OCR pada full image + warning |
| Gambar terlalu buram | Error: "OCR gagal mengekstrak teks" |
| PaddleOCR confidence rendah | Auto-fallback ke EasyOCR |
| LLM gagal parse JSON | Retry: manual JSON parsing dari response text |
| Format file tidak didukung | HTTP 400: "Format gambar tidak didukung" |

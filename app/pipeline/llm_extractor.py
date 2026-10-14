"""
Step 4: LLM Reconstruction — Menggunakan Gemini untuk memproses teks OCR
menjadi JSON terstruktur yang sudah dibersihkan dari typo dan noise.

Menggunakan strategi Few-Shot Prompting dengan 2 contoh realistis
(1 label Indonesia, 1 label English) yang mengandung typo OCR simulasi.

Gemini SDK otomatis memvalidasi output terhadap schema Pydantic via
`response_schema` parameter → eliminasi risiko JSON malformat.
"""
from google import genai
from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.schemas import NutritionFacts
import logging
import json

logger = logging.getLogger(__name__)

# ─── Lazy-loaded Gemini client ───
_client: genai.Client | None = None


def _get_gemini_client() -> genai.Client:
    """Lazy-load Gemini client dengan API key validation."""
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Please set it in your .env file. "
                "Get your key at https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# ───────────────────────────────────────────────────────────
# SYSTEM PROMPT — Few-Shot untuk Nutrition Facts Extraction
# ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Kamu adalah mesin ekstraksi data nutrisi yang sangat akurat. Tugasmu adalah mengekstrak informasi "Informasi Nilai Gizi" / "Nutrition Facts" dari teks mentah hasil OCR kemasan produk makanan/minuman.

## Aturan Penting:
1. Teks OCR sering mengandung TYPO dan karakter salah baca. Perbaiki secara diam-diam berdasarkan konteks:
   - "Kal0ri" → "Kalori", "Lem4k" → "Lemak", "Pr0tein" → "Protein"
   - "1O g" → "10 g", "2O%" → "20%", "l50 mg" → "150 mg"
   - "kka1" → "kkal", "mq" → "mg", "mcq" → "mcg"
2. Jika suatu field TIDAK ADA atau TIDAK TERBACA sama sekali dalam teks OCR, isi nilainya dengan null. JANGAN mengarang data.
3. Selalu sertakan SATUAN pada setiap angka (g, mg, mcg, kkal, ml, %).
4. Kelompokkan sub-nutrisi sebagai item terpisah (misal: "Lemak Jenuh" adalah item sendiri, bukan sub-field dari "Lemak Total").
5. Output HANYA valid JSON yang sesuai schema. Tidak boleh ada teks penjelasan, markdown, atau pembungkus lainnya.
6. Jika teks OCR tidak mengandung informasi nutrisi sama sekali, kembalikan JSON dengan semua field null dan nutrients list kosong."""


FEW_SHOT_EXAMPLES = """
## Contoh 1 (Label Indonesia — typo ringan):

### Input OCR:
<ocr_text>
lNF0RMASl NlLAl GlZl
Takaran Saji 1 bungkus (25q)
Jumlah Sajian per Kemasan : 1
Jumlah Per SaJian
Energl total 1O0 kka1
Energi dari Lemak 4O kkal
                         %AKG
Lem4k T0tal   5 g        7%
Lemak Jenuh   2 g        11%
Pr0tein       2 q        3%
Karb0hidrat t0tal 14 g   5%
Gula          1 g
Gar4m (Natrium) l50 mq   10%
</ocr_text>

### Output JSON:
{
  "product_name": null,
  "serving_size": "1 bungkus (25g)",
  "servings_per_package": "1",
  "calories": "100 kkal",
  "nutrients": [
    {"name": "Energi dari Lemak", "amount_per_serving": "40 kkal", "percent_daily_value": null},
    {"name": "Lemak Total", "amount_per_serving": "5 g", "percent_daily_value": "7%"},
    {"name": "Lemak Jenuh", "amount_per_serving": "2 g", "percent_daily_value": "11%"},
    {"name": "Protein", "amount_per_serving": "2 g", "percent_daily_value": "3%"},
    {"name": "Karbohidrat Total", "amount_per_serving": "14 g", "percent_daily_value": "5%"},
    {"name": "Gula", "amount_per_serving": "1 g", "percent_daily_value": null},
    {"name": "Garam (Natrium)", "amount_per_serving": "150 mg", "percent_daily_value": "10%"}
  ]
}

---

## Contoh 2 (Label English — typo berat):

### Input OCR:
<ocr_text>
NUTR1T10N  FACTS
Servinq S1ze  240m1  (1 cup)
Servinqs per Container  About 4
Ca1ories  12O
       Am0unt   %DV
Tot Fat    5g     6%
Sat. Fat   3g    15%
Trans F@t  Og
Cho1estero1  10mq   3%
S0dium    l2O mg    5%
T0t. C4rb  12g     4%
D1etary Fiber  0g   0%
T0ta1 Sug4rs   11g
Pr0te1n    8q
</ocr_text>

### Output JSON:
{
  "product_name": null,
  "serving_size": "240 ml (1 cup)",
  "servings_per_package": "About 4",
  "calories": "120 kkal",
  "nutrients": [
    {"name": "Total Fat", "amount_per_serving": "5 g", "percent_daily_value": "6%"},
    {"name": "Saturated Fat", "amount_per_serving": "3 g", "percent_daily_value": "15%"},
    {"name": "Trans Fat", "amount_per_serving": "0 g", "percent_daily_value": null},
    {"name": "Cholesterol", "amount_per_serving": "10 mg", "percent_daily_value": "3%"},
    {"name": "Sodium", "amount_per_serving": "120 mg", "percent_daily_value": "5%"},
    {"name": "Total Carbohydrate", "amount_per_serving": "12 g", "percent_daily_value": "4%"},
    {"name": "Dietary Fiber", "amount_per_serving": "0 g", "percent_daily_value": "0%"},
    {"name": "Total Sugars", "amount_per_serving": "11 g", "percent_daily_value": null},
    {"name": "Protein", "amount_per_serving": "8 g", "percent_daily_value": null}
  ]
}
"""


def reconstruct_nutrition_data(raw_ocr_text: str) -> NutritionFacts:
    """
    Mengirim teks OCR mentah ke Gemini untuk direkonstruksi
    menjadi NutritionFacts terstruktur.

    Pipeline:
    1. Bangun prompt user dengan <ocr_text> delimiters
    2. Kirim ke Gemini dengan few-shot context + structured output schema
    3. Gemini SDK otomatis memvalidasi response terhadap Pydantic model
    4. Jika parsing otomatis gagal, coba manual fallback

    Args:
        raw_ocr_text: Teks mentah gabungan dari OCR engine.

    Returns:
        NutritionFacts — Pydantic model yang sudah tervalidasi.

    Raises:
        ValueError: Jika LLM gagal menghasilkan JSON yang valid
                    setelah semua fallback dicoba.
    """
    client = _get_gemini_client()

    # Bangun prompt user dengan delimiters untuk mencegah prompt injection
    user_prompt = f"""Ekstrak data nutrisi dari teks OCR berikut:

<ocr_text>
{raw_ocr_text}
</ocr_text>

Berikan output JSON yang sesuai schema NutritionFacts."""

    models_to_try = [GEMINI_MODEL]
    for m in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash"]:
        if m not in models_to_try:
            models_to_try.append(m)

    last_error = None
    response = None

    for model_name in models_to_try:
        try:
            logger.info(f"Attempting LLM extraction using model: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    # Turn 1: System instruction + few-shot examples
                    {
                        "role": "user",
                        "parts": [{"text": SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLES}],
                    },
                    # Turn 2: Model acknowledgment (grounding)
                    {
                        "role": "model",
                        "parts": [
                            {
                                "text": "Saya siap mengekstrak data nutrisi dari teks OCR. "
                                "Silakan berikan teks OCR-nya."
                            }
                        ],
                    },
                    # Turn 3: Actual user input
                    {"role": "user", "parts": [{"text": user_prompt}]},
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": NutritionFacts,  # Pydantic schema enforcement
                    "temperature": 0.1,  # Low temperature for consistency
                },
            )

            # Gemini SDK otomatis memvalidasi via Pydantic
            nutrition_data: NutritionFacts = response.parsed

            logger.info(
                f"LLM extraction successful with {model_name} — "
                f"{len(nutrition_data.nutrients)} nutrients found, "
                f"calories: {nutrition_data.calories}, "
                f"serving_size: {nutrition_data.serving_size}"
            )

            return nutrition_data

        except Exception as e:
            logger.warning(f"LLM extraction failed on model {model_name}: {e}")
            last_error = e

            # Fallback: coba parse manual dari response text jika response ada
            if response is not None and hasattr(response, "text") and response.text:
                try:
                    raw_json = json.loads(response.text)
                    nutrition_data = NutritionFacts(**raw_json)
                    logger.info("Manual JSON parsing succeeded.")
                    return nutrition_data
                except Exception:
                    pass
            continue

    raise ValueError(
        f"Failed to reconstruct nutrition data from OCR text. "
        f"LLM error: {last_error}"
    )

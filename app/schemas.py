"""
Pydantic models for structured output from LLM and API responses.
Defines the NutritionFacts schema used by both the Gemini structured output
and the FastAPI response model.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class NutrientItem(BaseModel):
    """Representasi satu item nutrisi dalam tabel Nutrition Facts."""
    name: str = Field(
        description="Nama nutrisi (misal: Kalori, Lemak Total, Protein, Gula)"
    )
    amount_per_serving: Optional[str] = Field(
        default=None,
        description="Jumlah per sajian lengkap dengan satuan (misal: '120 kkal', '5 g', '150 mg')"
    )
    percent_daily_value: Optional[str] = Field(
        default=None,
        description="Persentase Angka Kecukupan Gizi / %AKG / %DV jika tersedia (misal: '8%')"
    )


class NutritionFacts(BaseModel):
    """Schema utama untuk data Nutrition Facts yang diekstrak dari gambar kemasan."""
    product_name: Optional[str] = Field(
        default=None,
        description="Nama produk jika terdeteksi di label"
    )
    serving_size: Optional[str] = Field(
        default=None,
        description="Takaran saji (misal: '1 bungkus (25g)', '240 ml')"
    )
    servings_per_package: Optional[str] = Field(
        default=None,
        description="Jumlah sajian per kemasan (misal: '1', 'About 4')"
    )
    calories: Optional[str] = Field(
        default=None,
        description="Energi total (misal: '120 kkal', '200 kcal')"
    )
    nutrients: List[NutrientItem] = Field(
        default_factory=list,
        description="Daftar semua nutrisi yang berhasil diekstrak dari tabel"
    )


class ExtractionResult(BaseModel):
    """
    Response model lengkap dari pipeline ekstraksi Nutrition Facts.
    Dikembalikan oleh endpoint POST /extract-nutrition.
    """
    success: bool = Field(
        description="True jika pipeline berhasil mengekstrak data, False jika gagal"
    )
    nutrition_data: Optional[NutritionFacts] = Field(
        default=None,
        description="Data nutrisi terstruktur hasil ekstraksi"
    )
    raw_ocr_text: Optional[str] = Field(
        default=None,
        description="Teks mentah hasil OCR sebelum diproses LLM"
    )
    ocr_engine_used: Optional[str] = Field(
        default=None,
        description="Engine OCR yang digunakan (PaddleOCR atau EasyOCR)"
    )
    ocr_confidence: Optional[float] = Field(
        default=None,
        description="Rata-rata confidence score dari OCR engine (0.0 - 1.0)"
    )
    detection_confidence: Optional[float] = Field(
        default=None,
        description="Confidence score dari deteksi YOLOv8 (0.0 - 1.0)"
    )
    detection_model: Optional[str] = Field(
        default="YOLOv8",
        description="Model deteksi yang digunakan (YOLOv8 atau Roboflow)"
    )
    annotated_image: Optional[str] = Field(
        default=None,
        description="Base64 data URL gambar dengan visualisasi bounding box deteksi"
    )
    cropped_image: Optional[str] = Field(
        default=None,
        description="Base64 data URL gambar hasil crop area tabel nutrisi"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Peringatan non-fatal selama proses pipeline"
    )
    error: Optional[str] = Field(
        default=None,
        description="Pesan error jika pipeline gagal"
    )

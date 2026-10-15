"""
Unit tests for the Pydantic schemas.
Validates that schemas accept valid data and reject invalid data correctly.
"""
import pytest
from app.schemas import NutrientItem, NutritionFacts, ExtractionResult


class TestNutrientItem:
    """Tests for NutrientItem schema."""

    def test_full_nutrient(self):
        """All fields populated."""
        item = NutrientItem(
            name="Lemak Total",
            amount_per_serving="5 g",
            percent_daily_value="7%",
        )
        assert item.name == "Lemak Total"
        assert item.amount_per_serving == "5 g"
        assert item.percent_daily_value == "7%"

    def test_minimal_nutrient(self):
        """Only required field (name)."""
        item = NutrientItem(name="Protein")
        assert item.name == "Protein"
        assert item.amount_per_serving is None
        assert item.percent_daily_value is None

    def test_missing_name_raises(self):
        """name is required."""
        with pytest.raises(Exception):
            NutrientItem()


class TestNutritionFacts:
    """Tests for NutritionFacts schema."""

    def test_full_nutrition_facts(self):
        """Complete nutrition facts data."""
        data = NutritionFacts(
            product_name="Indomie Goreng",
            serving_size="1 bungkus (85g)",
            servings_per_package="1",
            calories="380 kkal",
            nutrients=[
                NutrientItem(name="Lemak Total", amount_per_serving="14 g", percent_daily_value="20%"),
                NutrientItem(name="Protein", amount_per_serving="8 g", percent_daily_value="14%"),
            ],
        )
        assert data.product_name == "Indomie Goreng"
        assert len(data.nutrients) == 2

    def test_empty_nutrition_facts(self):
        """All optional fields can be None."""
        data = NutritionFacts()
        assert data.product_name is None
        assert data.serving_size is None
        assert data.calories is None
        assert data.nutrients == []

    def test_nutrients_default_empty_list(self):
        """nutrients should default to empty list, not None."""
        data = NutritionFacts()
        assert isinstance(data.nutrients, list)
        assert len(data.nutrients) == 0


class TestExtractionResult:
    """Tests for ExtractionResult schema."""

    def test_success_result(self):
        """Successful extraction result."""
        result = ExtractionResult(
            success=True,
            nutrition_data=NutritionFacts(calories="120 kkal"),
            raw_ocr_text="Kalori 120 kkal",
            ocr_engine_used="PaddleOCR",
            ocr_confidence=0.85,
            detection_confidence=0.92,
        )
        assert result.success is True
        assert result.nutrition_data.calories == "120 kkal"
        assert result.error is None

    def test_failure_result(self):
        """Failed extraction result."""
        result = ExtractionResult(
            success=False,
            error="OCR gagal mengekstrak teks",
            warnings=["Gambar buram"],
        )
        assert result.success is False
        assert result.error is not None
        assert len(result.warnings) == 1
        assert result.nutrition_data is None

    def test_warnings_default_empty(self):
        """warnings should default to empty list."""
        result = ExtractionResult(success=True)
        assert result.warnings == []

    def test_visual_detection_fields(self):
        """annotated_image, cropped_image, and detection_model should be supported."""
        result = ExtractionResult(
            success=True,
            detection_model="YOLOv8",
            annotated_image="data:image/jpeg;base64,dummyannotated",
            cropped_image="data:image/jpeg;base64,dummycrop",
        )
        assert result.detection_model == "YOLOv8"
        assert result.annotated_image == "data:image/jpeg;base64,dummyannotated"
        assert result.cropped_image == "data:image/jpeg;base64,dummycrop"

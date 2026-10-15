"""
Unit tests for the YOLOv8 detector module.
"""
import pytest
from PIL import Image
from app.pipeline.detector import detect_nutrition_table, get_yolo_model


class TestDetector:
    """Tests for YOLOv8 model loading and inference."""

    def test_model_loads_successfully(self):
        """Model should load and define classes."""
        model = get_yolo_model()
        assert model is not None
        assert isinstance(model.names, dict)
        assert 0 in model.names

    def test_detect_returns_valid_structure_or_none(self):
        """detect_nutrition_table should return either a structured dict or None."""
        test_img = Image.new("RGB", (320, 320), color=(255, 255, 255))
        result = detect_nutrition_table(test_img)
        if result is not None:
            assert "x" in result
            assert "y" in result
            assert "width" in result
            assert "height" in result
            assert "confidence" in result
            assert "annotated_image" in result
            assert result["model"] == "YOLOv8"
            assert isinstance(result["annotated_image"], Image.Image)

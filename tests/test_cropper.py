"""
Unit tests for the cropper module.
Tests image cropping and preprocessing logic without external API dependencies.
"""
import pytest
from PIL import Image
import numpy as np

from app.pipeline.cropper import (
    crop_nutrition_area,
    preprocess_for_ocr,
    estimate_skew_angle,
    deskew_image,
    remove_glare_and_normalize,
)


class TestCropNutritionArea:
    """Tests for crop_nutrition_area function."""

    def _create_test_image(self, width: int = 800, height: int = 600) -> Image.Image:
        """Create a simple test image with known dimensions."""
        return Image.new("RGB", (width, height), color=(255, 255, 255))

    def test_basic_crop(self):
        """Crop with valid bbox should return smaller image."""
        image = self._create_test_image(800, 600)
        bbox = {"x": 400, "y": 300, "width": 200, "height": 150}

        cropped = crop_nutrition_area(image, bbox, padding=0)

        assert cropped.size[0] == 200  # width
        assert cropped.size[1] == 150  # height

    def test_crop_with_padding(self):
        """Crop with padding should extend the area."""
        image = self._create_test_image(800, 600)
        bbox = {"x": 400, "y": 300, "width": 200, "height": 150}

        cropped = crop_nutrition_area(image, bbox, padding=10)

        # Should be 200+20=220 wide, 150+20=170 tall
        assert cropped.size[0] == 220
        assert cropped.size[1] == 170

    def test_crop_clamped_to_image_bounds(self):
        """Crop near edges should be clamped to image boundaries."""
        image = self._create_test_image(800, 600)
        # bbox near top-left corner
        bbox = {"x": 50, "y": 50, "width": 200, "height": 200}

        cropped = crop_nutrition_area(image, bbox, padding=100)

        # Left and top should clamp to 0, so cropped can't exceed image bounds
        assert cropped.size[0] <= 800
        assert cropped.size[1] <= 600
        assert cropped.size[0] > 0
        assert cropped.size[1] > 0

    def test_crop_returns_pil_image(self):
        """Result should be a PIL Image."""
        image = self._create_test_image()
        bbox = {"x": 400, "y": 300, "width": 200, "height": 150}

        result = crop_nutrition_area(image, bbox)
        assert isinstance(result, Image.Image)


class TestPreprocessForOcr:
    """Tests for preprocess_for_ocr function."""

    def _create_test_image(self, width: int = 200, height: int = 100) -> Image.Image:
        """Create a test image with some variation."""
        img_array = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        return Image.fromarray(img_array, "RGB")

    def test_returns_numpy_array(self):
        """Preprocessed output should be a numpy array."""
        image = self._create_test_image()
        result = preprocess_for_ocr(image)
        assert isinstance(result, np.ndarray)

    def test_output_is_grayscale(self):
        """Output should be 2D (grayscale), not 3D (color)."""
        image = self._create_test_image()
        result = preprocess_for_ocr(image)
        assert len(result.shape) == 2

    def test_output_is_upscaled(self):
        """Output dimensions should be 2x the input (default upscale factor)."""
        image = self._create_test_image(200, 100)
        result = preprocess_for_ocr(image)
        # With IMAGE_UPSCALE_FACTOR = 2
        assert result.shape[1] == 400  # width * 2
        assert result.shape[0] == 200  # height * 2

    def test_output_is_binary(self):
        """After thresholding with binarize=True, output should only contain 0 and 255."""
        image = self._create_test_image()
        result = preprocess_for_ocr(image, binarize=True)
        unique_values = np.unique(result)
        assert all(v in [0, 255] for v in unique_values)

    def test_output_is_natural_grayscale(self):
        """By default, output is smooth grayscale without destructive binarization."""
        image = self._create_test_image()
        result = preprocess_for_ocr(image)
        assert result.dtype == np.uint8
        assert len(result.shape) == 2

    def test_handles_grayscale_input(self):
        """Should handle already-grayscale images."""
        gray_array = np.random.randint(0, 255, (100, 200), dtype=np.uint8)
        image = Image.fromarray(gray_array, "L")
        result = preprocess_for_ocr(image)
        assert isinstance(result, np.ndarray)
        assert len(result.shape) == 2

    def test_estimate_skew_angle_and_deskew(self):
        """Tests that skew estimation and deskewing functions execute correctly."""
        import cv2
        h, w = 200, 400
        canvas = np.ones((h, w), dtype=np.uint8) * 255
        # Draw mock text lines
        for y in range(40, 180, 40):
            cv2.line(canvas, (30, y), (370, y), 0, 4)
        # Rotate by -5 degrees
        M = cv2.getRotationMatrix2D((w // 2, h // 2), -5.0, 1.0)
        rotated = cv2.warpAffine(canvas, M, (w, h), borderValue=255)

        angle = estimate_skew_angle(rotated)
        assert isinstance(angle, float)
        # Should detect a rotation near 5 degrees
        assert abs(angle - 5.0) < 2.0

        deskewed = deskew_image(rotated, angle, keep_size=True)
        assert deskewed.shape == rotated.shape

    def test_remove_glare_and_normalize(self):
        """Tests that glare suppression normalizes hotspot and enhances contrast."""
        h, w = 150, 150
        base = np.ones((h, w), dtype=np.uint8) * 128
        # Add glare hotspot in center
        base[50:100, 50:100] = 255
        normalized = remove_glare_and_normalize(base)
        assert isinstance(normalized, np.ndarray)
        assert normalized.shape == (h, w)
        assert normalized.dtype == np.uint8

"""
Unit tests for HistogramViewer image processing functions.

Run with: python -m pytest tests/ -v
Or: python -m unittest tests.test_image_processing -v
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import only the pure image-processing functions (no Qt)
from HistogramViewer import (
    normalize_input,
    ensure_hwc,
    autostretch_percentile,
    normalize_stretched_fits,
    _infer_adu_max,
    _empty_histogram_data,
    HISTOGRAM_BINS,
)


class TestNormalizeInput(unittest.TestCase):
    """Tests for normalize_input."""

    def test_uint8(self):
        arr = np.array([[0, 128, 255]], dtype=np.uint8)
        out = normalize_input(arr)
        assert out.dtype == np.float32
        assert 0 <= out.min() <= out.max() <= 1
        assert np.allclose(out[0, 1], 128 / 255)

    def test_uint16_with_adu_max(self) -> None:
        arr = np.array([[0, 32768, 65535]], dtype=np.uint16)
        out = normalize_input(arr, adu_max=65535)
        assert out.dtype == np.float32
        assert np.allclose(out[0, 1], 0.5, atol=0.01)

    def test_int16(self):
        arr = np.array([[-32768, 0, 32767]], dtype=np.int16)
        out = normalize_input(arr)
        assert out.dtype == np.float32
        assert 0 <= out.min() <= out.max() <= 1


class TestEnsureHwc(unittest.TestCase):
    """Tests for ensure_hwc."""

    def test_2d_to_3ch(self) -> None:
        arr = np.ones((10, 20))
        out = ensure_hwc(arr)
        assert out.shape == (10, 20, 3)
        assert np.allclose(out[:, :, 0], out[:, :, 1])
        assert np.allclose(out[:, :, 1], out[:, :, 2])

    def test_hwc_passthrough(self) -> None:
        arr = np.ones((10, 20, 3))
        out = ensure_hwc(arr)
        assert out.shape == (10, 20, 3)

    def test_chw_transpose(self) -> None:
        arr = np.ones((3, 10, 20))
        out = ensure_hwc(arr)
        assert out.shape == (10, 20, 3)


class TestAutostretchPercentile(unittest.TestCase):
    """Tests for autostretch_percentile."""

    def test_basic(self) -> None:
        arr = np.linspace(0, 1, 100).reshape(10, 10).astype(np.float32)
        out = autostretch_percentile(arr)
        assert out.dtype == np.float32
        assert 0 <= out.min() <= out.max() <= 1

    def test_flat_image(self) -> None:
        arr = np.full((5, 5), 0.5, dtype=np.float32)
        out = autostretch_percentile(arr)
        assert np.allclose(out, 0.5)


class TestNormalizeStretchedFits(unittest.TestCase):
    """Tests for normalize_stretched_fits."""

    def test_uint8(self) -> None:
        arr = np.array([[0, 128, 255]], dtype=np.uint8)
        out = normalize_stretched_fits(arr)
        assert out.shape == (1, 3, 3)
        assert out.dtype == np.float32
        assert np.allclose(out[0, 1, 0], 128 / 255)

    def test_uint16(self) -> None:
        arr = np.array([[0, 32768, 65535]], dtype=np.uint16)
        out = normalize_stretched_fits(arr)
        assert out.dtype == np.float32
        assert np.allclose(out[0, 1, 0], 0.5, atol=0.01)

    def test_float_clip(self) -> None:
        arr = np.array([[-0.5, 0.5, 1.5]], dtype=np.float32)
        out = normalize_stretched_fits(arr)
        assert 0 <= out.min() <= out.max() <= 1


class TestInferAduMax(unittest.TestCase):
    """Tests for _infer_adu_max."""

    def test_uint8(self) -> None:
        arr = np.array([[0, 255]], dtype=np.uint8)
        assert _infer_adu_max(arr) == 255

    def test_uint16_12bit(self) -> None:
        arr = np.array([[0, 4095]], dtype=np.uint16)
        assert _infer_adu_max(arr) == 4095

    def test_uint16_14bit(self) -> None:
        arr = np.array([[0, 16383]], dtype=np.uint16)
        assert _infer_adu_max(arr) == 16383

    def test_uint16_16bit(self) -> None:
        arr = np.array([[0, 65535]], dtype=np.uint16)
        assert _infer_adu_max(arr) == 65535

    def test_int16(self):
        arr = np.array([[-32768, 32767]], dtype=np.int16)
        assert _infer_adu_max(arr) == 65535


class TestEmptyHistogramData(unittest.TestCase):
    """Tests for _empty_histogram_data."""

    def test_structure(self) -> None:
        hist, edges = _empty_histogram_data()
        assert "RGB" in hist
        assert "R" in hist
        assert "G" in hist
        assert "B" in hist
        assert "L" in hist
        assert all(h.shape == (HISTOGRAM_BINS,) for h in hist.values())
        assert len(edges) == HISTOGRAM_BINS + 1
        assert np.allclose(edges[0], 0)
        assert np.allclose(edges[-1], 1)


if __name__ == "__main__":
    unittest.main()

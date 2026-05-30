"""Tests for core.vision preprocessing and bbox normalization (no API calls)."""

import io

import pytest
from PIL import Image

from core.vision import (
    DetectedObject,
    VisionAnalysis,
    _normalize_bboxes,
    _to_jpeg_bytes,
)


def _analysis(bbox):
    return VisionAnalysis(
        scene_summary="",
        objects=[DetectedObject(label="x", confidence=0.9, bbox=bbox)],
        risks_or_opportunities=[],
        suggested_actions=[],
        confidence_notes="",
    )


def test_normalize_reorders_and_rescales_0_1000():
    # Gemini emits [ymin, xmin, ymax, xmax] on a 0-1000 scale.
    out = _normalize_bboxes(_analysis([100, 200, 300, 400]))
    # → reorder to [xmin, ymin, xmax, ymax] then /1000.
    assert out.objects[0].bbox == pytest.approx([0.2, 0.1, 0.4, 0.3])


def test_normalize_reorders_when_already_0_1():
    out = _normalize_bboxes(_analysis([0.1, 0.2, 0.3, 0.4]))
    assert out.objects[0].bbox == pytest.approx([0.2, 0.1, 0.4, 0.3])


def test_normalize_leaves_none_and_malformed_untouched():
    assert _normalize_bboxes(_analysis(None)).objects[0].bbox is None
    assert _normalize_bboxes(_analysis([0.1, 0.2])).objects[0].bbox == [0.1, 0.2]


def _jpeg_in(mode, size):
    buf = io.BytesIO()
    Image.new(mode, size).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("mode", ["RGBA", "P", "L", "RGB"])
@pytest.mark.parametrize("size", [(800, 600), (600, 800), (500, 500), (4000, 200)])
def test_to_jpeg_normalizes_modes_and_sizes(mode, size):
    out = _to_jpeg_bytes(_jpeg_in(mode, size))
    assert out[:2] == b"\xff\xd8"  # JPEG SOI marker
    img = Image.open(io.BytesIO(out))
    assert img.mode == "RGB"
    assert max(img.size) <= 2048


def test_to_jpeg_downscales_oversized():
    img = Image.open(io.BytesIO(_to_jpeg_bytes(_jpeg_in("RGB", (3000, 1500)))))
    assert max(img.size) == 2048


def test_to_jpeg_applies_exif_orientation():
    # Orientation tag 6 → a stored WxH image should display as HxW after transpose.
    src = Image.new("RGB", (100, 40), "red")
    exif = src.getexif()
    exif[274] = 6  # 274 = Orientation
    buf = io.BytesIO()
    src.save(buf, format="JPEG", exif=exif)

    out = Image.open(io.BytesIO(_to_jpeg_bytes(buf.getvalue())))
    assert out.size == (40, 100)

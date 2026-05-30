"""Tests for the Pillow annotator helpers and edge cases (core.annotator)."""

from PIL import Image, ImageDraw

from core.annotator import (
    _intersects,
    _load_font,
    _text_width,
    _truncate,
    _valid_bbox,
    annotate_image,
)
from core.vision import DetectedObject, VisionAnalysis


def _analysis(objects):
    return VisionAnalysis(
        scene_summary="",
        objects=objects,
        risks_or_opportunities=[],
        suggested_actions=[],
        confidence_notes="",
    )


def test_valid_bbox_clamps_to_unit_range():
    assert _valid_bbox([-0.1, 0.0, 1.2, 1.0]) == [0.0, 0.0, 1.0, 1.0]


def test_valid_bbox_rejects_degenerate_and_malformed():
    assert _valid_bbox([0.5, 0.5, 0.5, 0.9]) is None  # x1 <= x0
    assert _valid_bbox([0.1, 0.2, 0.3]) is None  # wrong length
    assert _valid_bbox(None) is None


def test_intersects():
    assert _intersects([0, 0, 10, 10], [5, 5, 15, 15]) is True
    assert _intersects([0, 0, 10, 10], [10, 0, 20, 10]) is False  # touching, not overlapping
    assert _intersects([0, 0, 10, 10], [20, 20, 30, 30]) is False


def test_truncate_adds_ellipsis_and_fits_budget():
    img = Image.new("RGBA", (400, 200))
    draw = ImageDraw.Draw(img)
    font = _load_font(20)
    out = _truncate(draw, "a very long object label that will not fit", font, 60)
    assert out.endswith("…")
    assert _text_width(draw, out, font) <= 60


def test_truncate_leaves_short_text_unchanged():
    img = Image.new("RGBA", (400, 200))
    draw = ImageDraw.Draw(img)
    font = _load_font(20)
    assert _truncate(draw, "mug", font, 300) == "mug"


def test_empty_objects_returns_same_size_image():
    img = Image.new("RGB", (320, 240), "white")
    out = annotate_image(img, _analysis([]))
    assert out.size == (320, 240)


def test_all_invalid_bboxes_render_without_error():
    # No usable bbox → legend fallback path; must not blank or crash.
    objs = [DetectedObject(label="mug", confidence=0.7, bbox=None)]
    out = annotate_image(Image.new("RGB", (320, 240), "white"), _analysis(objs))
    assert out.size == (320, 240)


def test_overlapping_bboxes_render_without_error():
    objs = [
        DetectedObject(label="mug", confidence=0.7, bbox=[0.1, 0.1, 0.5, 0.5]),
        DetectedObject(label="cup", confidence=0.6, bbox=[0.1, 0.1, 0.5, 0.5]),
    ]
    out = annotate_image(Image.new("RGB", (640, 480), "white"), _analysis(objs))
    assert out.size == (640, 480)

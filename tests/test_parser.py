"""Tests for the fallback parser (core.parser)."""

from core.parser import parse_raw_json, safe_to_dict
from core.vision import DetectedObject, VisionAnalysis


def test_strips_markdown_fences():
    raw = '```json\n{"scene_summary": "a tidy desk"}\n```'
    out = parse_raw_json(raw)
    assert out.scene_summary == "a tidy desk"


def test_missing_fields_get_defaults():
    out = parse_raw_json('{"scene_summary": "hi"}')
    assert out.scene_summary == "hi"
    assert out.objects == []
    assert out.risks_or_opportunities == []
    assert out.suggested_actions == []
    assert out.confidence_notes == ""


def test_null_fields_fall_back_to_defaults():
    out = parse_raw_json('{"scene_summary": "hi", "objects": null}')
    assert out.objects == []


def test_unparseable_returns_empty_with_note():
    out = parse_raw_json("this is not json at all")
    assert out.scene_summary == ""
    assert out.confidence_notes == "Model output could not be parsed as JSON."


def test_non_object_top_level_falls_back():
    out = parse_raw_json("[1, 2, 3]")
    assert out.confidence_notes == "Model output could not be parsed as JSON."


def test_safe_to_dict_drops_none_bbox():
    analysis = VisionAnalysis(
        scene_summary="",
        objects=[DetectedObject(label="mug", confidence=0.8, bbox=None)],
        risks_or_opportunities=[],
        suggested_actions=[],
        confidence_notes="",
    )
    d = safe_to_dict(analysis)
    assert "bbox" not in d["objects"][0]

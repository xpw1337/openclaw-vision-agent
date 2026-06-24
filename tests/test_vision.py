"""Tests for core.vision preprocessing and bbox normalization (no API calls)."""

import io

import pytest
from PIL import Image

import core.vision as vision
from core.vision import (
    DEFAULT_SYSTEM_PROMPT,
    DetectedObject,
    VisionAnalysis,
    _normalize_bboxes,
    _resolve_system_prompt,
    _to_jpeg_bytes,
    analyze_image,
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


# --- system prompt resolution + zone injection -----------------------------


def test_resolve_system_prompt_defaults_to_surveillance(monkeypatch):
    monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
    assert _resolve_system_prompt(None) == DEFAULT_SYSTEM_PROMPT


def test_resolve_system_prompt_env_override(monkeypatch):
    monkeypatch.setenv("SYSTEM_PROMPT", "CUSTOM PROMPT")
    assert _resolve_system_prompt(None) == "CUSTOM PROMPT"


def test_resolve_system_prompt_injects_zone(monkeypatch):
    monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
    out = _resolve_system_prompt("loading dock")
    assert out.startswith(DEFAULT_SYSTEM_PROMPT)
    assert "loading dock" in out


class _FakeResponse:
    def __init__(self, parsed):
        self.parsed = parsed
        self.prompt_feedback = None
        self.candidates = []


class _FakeModels:
    def __init__(self, sink):
        self._sink = sink

    def generate_content(self, **kwargs):
        self._sink.update(kwargs)
        analysis = VisionAnalysis(
            scene_summary="ok",
            objects=[],
            risks_or_opportunities=[],
            suggested_actions=[],
            confidence_notes="",
        )
        return _FakeResponse(analysis)


class _FakeClient:
    def __init__(self, sink, **_kwargs):
        self.models = _FakeModels(sink)


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buf, format="PNG")
    return buf.getvalue()


def test_analyze_image_passes_zone_context_to_model(monkeypatch):
    sink = {}
    monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
    monkeypatch.setattr(vision.genai, "Client", lambda **kw: _FakeClient(sink, **kw))

    analyze_image(_png_bytes(), zone="dock")

    system_instruction = sink["config"].system_instruction
    assert "dock" in system_instruction
    assert system_instruction.startswith(DEFAULT_SYSTEM_PROMPT)


def test_analyze_image_uses_env_prompt(monkeypatch):
    sink = {}
    monkeypatch.setenv("SYSTEM_PROMPT", "CUSTOM PROMPT")
    monkeypatch.setattr(vision.genai, "Client", lambda **kw: _FakeClient(sink, **kw))

    analyze_image(_png_bytes())

    assert sink["config"].system_instruction == "CUSTOM PROMPT"

"""Fallback parser — Iteration 2 defense layer.

When the Gemini SDK can't hand us a parsed object, we get raw text that may be
wrapped in markdown fences or missing fields. `parse_raw_json` recovers a valid
`VisionAnalysis` from it, filling gaps with sensible defaults rather than raising.
"""

import json
import re

from core.vision import VisionAnalysis

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)

_DEFAULTS = {
    "scene_summary": "",
    "objects": [],
    "risks_or_opportunities": [],
    "suggested_actions": [],
    "confidence_notes": "",
}


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    text = _FENCE_RE.sub("", text)
    return text.strip()


def parse_raw_json(raw: str) -> VisionAnalysis:
    """Best-effort parse of model text into a VisionAnalysis.

    Strips markdown fences, parses JSON, and fills any missing top-level field
    with a default. On unparseable input, returns an empty analysis whose
    confidence_notes records the failure.
    """
    text = _strip_fences(raw or "")
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("top-level JSON is not an object")
    except (json.JSONDecodeError, ValueError):
        return VisionAnalysis(
            scene_summary="",
            objects=[],
            risks_or_opportunities=[],
            suggested_actions=[],
            confidence_notes="Model output could not be parsed as JSON.",
        )

    merged = {**_DEFAULTS, **{k: v for k, v in data.items() if v is not None}}
    return VisionAnalysis(**merged)


def safe_to_dict(analysis: VisionAnalysis) -> dict:
    """Dict form for display, dropping None values (e.g. omitted bboxes)."""
    return analysis.model_dump(exclude_none=True)

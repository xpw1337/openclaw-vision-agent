"""Vision call — Gemini 3.5 Flash structured outputs.

Pydantic schema + Gemini 3.5 Flash structured outputs. `analyze_image` returns a
typed `VisionAnalysis`. If the SDK can't give us a parsed object we fall back to
the lenient parser in `core.parser`. Inputs are normalized for orientation and
mode before they reach the model, and content/safety blocks surface as a
`ContentBlockedError` rather than an empty or confusing result.
"""

import io
import os

from google import genai
from google.genai import types
from PIL import Image, ImageOps
from pydantic import BaseModel

_MAX_EDGE = 2048
_MODEL = "gemini-3.5-flash"
_TIMEOUT_MS = 30_000

# Finish/block reasons that mean the model refused on content or safety grounds,
# as opposed to a normal completion (STOP, MAX_TOKENS). Compared by name so this
# is robust whether the SDK hands us a str-enum member or a bare string.
_BLOCKING_REASONS = frozenset(
    {
        "SAFETY",
        "RECITATION",
        "PROHIBITED_CONTENT",
        "BLOCKLIST",
        "SPII",
        "JAILBREAK",
        "MODEL_ARMOR",
        "IMAGE_SAFETY",
        "IMAGE_PROHIBITED_CONTENT",
        "IMAGE_RECITATION",
    }
)


class ContentBlockedError(Exception):
    """Raised when Gemini refuses to analyze an image on content/safety grounds."""


class DetectedObject(BaseModel):
    label: str
    confidence: float
    bbox: list[float] | None = None  # normalized [x0, y0, x1, y1] in [0,1]


class VisionAnalysis(BaseModel):
    scene_summary: str
    objects: list[DetectedObject]
    risks_or_opportunities: list[str]
    suggested_actions: list[str]
    confidence_notes: str


SYSTEM_PROMPT = (
    "You are OpenClaw Vision Agent, operating in Desk Safety Assistant mode. "
    "You analyze a photo of a workspace and report what you see, the safety "
    "risks or opportunities present, and concrete actions the person could take.\n"
    "\n"
    "Ground everything in THIS specific image. Never give generic advice that "
    "isn't tied to something you actually observe.\n"
    "- GOOD: 'Coffee mug sitting at the laptop's left edge — a spill there would "
    "reach the keyboard. Move the mug to the right of the keyboard, away from the "
    "machine.'\n"
    "- BAD: 'Keep your desk tidy and stay organized.' (generic, not grounded in "
    "anything visible)\n"
    "\n"
    "Rules:\n"
    "1. Every suggested_action MUST reference at least one object that appears in "
    "your objects list. If you can't tie an action to a visible object, omit it.\n"
    "2. confidence_notes must describe the ACTUAL image conditions that affected "
    "your read — lighting, camera angle, occlusion, blur, or cropping — not "
    "boilerplate caveats.\n"
    "3. Bounding boxes are optional. Use the format [ymin, xmin, ymax, xmax] with "
    "each value normalized to [0,1]. Omit the bbox field for an object whose "
    "location you are unsure of.\n"
    "4. Be honest about uncertainty: confidences and bounding boxes are estimates, "
    "not precise measurements."
)


def _to_jpeg_bytes(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    # Respect EXIF orientation so phone photos are upright, and normalize every
    # mode (RGBA / palette / grayscale) to RGB before JPEG encoding.
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    longest = max(img.size)
    if longest > _MAX_EDGE:
        scale = _MAX_EDGE / longest
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _normalize_bboxes(analysis: VisionAnalysis) -> VisionAnalysis:
    """Coerce Gemini's boxes into normalized [x0, y0, x1, y1] in [0,1].

    Gemini emits boxes y-axis first as [ymin, xmin, ymax, xmax], and is
    inconsistent about scale — sometimes [0,1], sometimes [0,1000] — regardless
    of the prompt. The rest of the app (annotator, raw-JSON display, sample
    outputs) expects the [x0, y0, x1, y1] order in [0,1] documented on
    DetectedObject.bbox, so we reorder and rescale once here at the boundary.
    Any coordinate above 1.0 means the box is on the 0-1000 scale.
    """
    for obj in analysis.objects:
        if obj.bbox is None or len(obj.bbox) != 4:
            continue
        ymin, xmin, ymax, xmax = obj.bbox
        box = [xmin, ymin, xmax, ymax]
        if any(v > 1.0 for v in box):
            box = [v / 1000.0 for v in box]
        obj.bbox = box
    return analysis


def _reason_name(reason) -> str | None:
    """Normalize a finish/block reason (str-enum member or bare string) to its name."""
    if reason is None:
        return None
    return getattr(reason, "name", str(reason))


def _check_blocked(response) -> None:
    """Raise ContentBlockedError if the model refused on content/safety grounds.

    Looks at the prompt-level block reason and the first candidate's finish
    reason. A normal completion (STOP / MAX_TOKENS) or no candidates at all is
    left alone — the latter falls through to the parser's empty-analysis path.
    """
    feedback = getattr(response, "prompt_feedback", None)
    block_reason = _reason_name(getattr(feedback, "block_reason", None))
    if block_reason and block_reason in _BLOCKING_REASONS:
        raise ContentBlockedError(block_reason)

    candidates = getattr(response, "candidates", None) or []
    if candidates:
        finish = _reason_name(getattr(candidates[0], "finish_reason", None))
        if finish and finish in _BLOCKING_REASONS:
            raise ContentBlockedError(finish)


def analyze_image(image_bytes: bytes) -> VisionAnalysis:
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        http_options=types.HttpOptions(timeout=_TIMEOUT_MS),
    )
    jpeg = _to_jpeg_bytes(image_bytes)
    response = client.models.generate_content(
        model=_MODEL,
        contents=[types.Part.from_bytes(data=jpeg, mime_type="image/jpeg")],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            max_output_tokens=2000,
            response_mime_type="application/json",
            response_schema=VisionAnalysis,
        ),
    )
    _check_blocked(response)
    if response.parsed is not None:
        return _normalize_bboxes(response.parsed)

    # Lazy import avoids a circular import at module load (parser imports VisionAnalysis).
    from core.parser import parse_raw_json

    return _normalize_bboxes(parse_raw_json(response.text))

"""Vision call — Iteration 2 spec-complete.

Pydantic schema + Gemini 3.5 Flash structured outputs. `analyze_image` returns a
typed `VisionAnalysis`. If the SDK can't give us a parsed object we fall back to
the lenient parser in `core.parser`.
"""

import io
import os

from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel

_MAX_EDGE = 2048
_MODEL = "gemini-3.5-flash"


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
    "risks or opportunities present, and concrete actions the person could take. "
    "Be specific to THIS image — never give generic advice not grounded in what "
    "you actually see. "
    "Bounding boxes are optional. The format is normalized [x0, y0, x1, y1] with "
    "each value in [0,1]. Omit the bbox field for an object if you are uncertain "
    "about its location. "
    "Be honest about uncertainty: confidences and bounding boxes are estimates, "
    "not precise measurements."
)


def _to_jpeg_bytes(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    longest = max(img.size)
    if longest > _MAX_EDGE:
        scale = _MAX_EDGE / longest
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def analyze_image(image_bytes: bytes) -> VisionAnalysis:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
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
    if response.parsed is not None:
        return response.parsed

    # Lazy import avoids a circular import at module load (parser imports VisionAnalysis).
    from core.parser import parse_raw_json

    return parse_raw_json(response.text)

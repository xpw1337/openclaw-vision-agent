"""Minimum vision call — Iteration 1 walking skeleton.

One function: take image bytes, send to Gemini 3.5 Flash, return raw response text.
No Pydantic, no parsing, no error handling beyond what the SDK does itself.
"""

import io
import os

from google import genai
from google.genai import types
from PIL import Image

_MAX_EDGE = 2048
_MODEL = "gemini-3.5-flash"

SYSTEM_PROMPT = (
    "You are OpenClaw Vision Agent in Desk Safety Assistant mode. "
    "Describe the scene in this image as JSON with these top-level fields: "
    "scene_summary (string), objects (list of strings), "
    "risks (list of strings), actions (list of strings). "
    "Be specific to what you actually see — no generic advice."
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


def analyze_image(image_bytes: bytes) -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    jpeg = _to_jpeg_bytes(image_bytes)
    response = client.models.generate_content(
        model=_MODEL,
        contents=[types.Part.from_bytes(data=jpeg, mime_type="image/jpeg")],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            max_output_tokens=2000,
        ),
    )
    return response.text

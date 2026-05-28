"""Minimum vision call — Iteration 1 walking skeleton.

One function: take image bytes, send to gpt-4o, return raw response text.
No Pydantic, no parsing, no error handling beyond what the SDK does itself.
"""

import base64
import io

from openai import OpenAI
from PIL import Image

_MAX_EDGE = 2048

SYSTEM_PROMPT = (
    "You are OpenClaw Vision Agent in Desk Safety Assistant mode. "
    "Describe the scene in this image as JSON with these top-level fields: "
    "scene_summary (string), objects (list of strings), "
    "risks (list of strings), actions (list of strings). "
    "Be specific to what you actually see — no generic advice."
)


def _encode_image(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    longest = max(img.size)
    if longest > _MAX_EDGE:
        scale = _MAX_EDGE / longest
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def analyze_image(image_bytes: bytes) -> str:
    client = OpenAI(timeout=30.0)
    b64 = _encode_image(image_bytes)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        temperature=0.2,
        max_tokens=2000,
    )
    return response.choices[0].message.content

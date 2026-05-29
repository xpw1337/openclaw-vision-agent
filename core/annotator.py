"""Pillow annotator — Iteration 2 visual output.

`annotate_image` draws the model's findings onto the photo. If any object carries
a usable bounding box we draw boxes; otherwise we fall back to a numbered legend
panel in the top-right corner. Drawing happens on a transparent overlay that is
alpha-composited onto an RGBA copy so the semi-transparent fills blend cleanly.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from core.vision import VisionAnalysis

_PALETTE = [
    "#E63946", "#F1A208", "#2A9D8F", "#264653",
    "#8338EC", "#06A77D", "#F4A261", "#4361EE",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _valid_bbox(bbox: list[float] | None) -> list[float] | None:
    """Clamp to [0,1] and return only if it describes a real (x0<x1, y0<y1) box."""
    if not bbox or len(bbox) != 4:
        return None
    try:
        x0, y0, x1, y1 = (min(1.0, max(0.0, float(v))) for v in bbox)
    except (TypeError, ValueError):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def _draw_bboxes(overlay, draw, w, h, font, objects) -> None:
    for i, obj in enumerate(objects):
        bbox = _valid_bbox(obj.bbox)
        if bbox is None:
            continue
        rgb = _hex_to_rgb(_PALETTE[i % len(_PALETTE)])
        x0, y0, x1, y1 = (bbox[0] * w, bbox[1] * h, bbox[2] * w, bbox[3] * h)
        draw.rectangle([x0, y0, x1, y1], fill=(*rgb, 64), outline=(*rgb, 255), width=3)

        label = f"{obj.label} {int(obj.confidence * 100)}%"
        tx0, ty0, tx1, ty1 = draw.textbbox((0, 0), label, font=font)
        tw, th = tx1 - tx0, ty1 - ty0
        ly = max(0, y0 - th - 4)
        draw.rectangle([x0, ly, x0 + tw + 6, ly + th + 4], fill=(*rgb, 230))
        draw.text((x0 + 3, ly + 2), label, fill=(255, 255, 255, 255), font=font)


def _draw_legend(overlay, draw, w, h, font, objects) -> None:
    lines = [f"{i + 1}. {o.label} {int(o.confidence * 100)}%" for i, o in enumerate(objects)]
    widths, height = [], 0
    for line in lines:
        lx0, ly0, lx1, ly1 = draw.textbbox((0, 0), line, font=font)
        widths.append(lx1 - lx0)
        height = max(height, ly1 - ly0)

    pad = 10
    line_gap = 6
    bullet = height
    panel_w = (max(widths) if widths else 0) + bullet + pad * 3
    panel_h = len(lines) * (height + line_gap) - line_gap + pad * 2
    px0 = w - panel_w - pad
    py0 = pad
    draw.rectangle([px0, py0, px0 + panel_w, py0 + panel_h], fill=(0, 0, 0, 180))

    y = py0 + pad
    for i, line in enumerate(lines):
        rgb = _hex_to_rgb(_PALETTE[i % len(_PALETTE)])
        cy = y + height / 2
        bx = px0 + pad
        draw.ellipse([bx, cy - bullet / 2, bx + bullet, cy + bullet / 2], fill=(*rgb, 255))
        draw.text((bx + bullet + pad, y), line, fill=(255, 255, 255, 255), font=font)
        y += height + line_gap


def annotate_image(image: Image.Image, analysis: VisionAnalysis) -> Image.Image:
    base = image.convert("RGBA").copy()
    if not analysis.objects:
        return base

    w, h = base.size
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(max(14, min(w, h) // 40))

    has_bbox = any(_valid_bbox(o.bbox) is not None for o in analysis.objects)
    if has_bbox:
        _draw_bboxes(overlay, draw, w, h, font, analysis.objects)
    else:
        _draw_legend(overlay, draw, w, h, font, analysis.objects)

    return Image.alpha_composite(base, overlay)

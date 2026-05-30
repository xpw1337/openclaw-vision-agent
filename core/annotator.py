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


def _text_width(draw, text: str, font) -> float:
    x0, _, x1, _ = draw.textbbox((0, 0), text, font=font)
    return x1 - x0


def _truncate(draw, text: str, font, max_w: float) -> str:
    """Trim `text` with a trailing ellipsis until it renders within `max_w`."""
    if _text_width(draw, text, font) <= max_w:
        return text
    ellipsis = "…"
    # Drop characters until the text plus an ellipsis fits; never return empty.
    for end in range(len(text) - 1, 0, -1):
        candidate = text[:end].rstrip() + ellipsis
        if _text_width(draw, candidate, font) <= max_w:
            return candidate
    return ellipsis


def _intersects(a: list[float], b: list[float]) -> bool:
    """True if axis-aligned rects a=[x0,y0,x1,y1] and b overlap."""
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


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
    min_label_w = max(font.size * 4 if hasattr(font, "size") else 56, 56)
    placed: list[list[float]] = []  # label rects already drawn, for collision checks

    for i, obj in enumerate(objects):
        bbox = _valid_bbox(obj.bbox)
        if bbox is None:
            continue
        rgb = _hex_to_rgb(_PALETTE[i % len(_PALETTE)])
        x0, y0, x1, y1 = (bbox[0] * w, bbox[1] * h, bbox[2] * w, bbox[3] * h)
        draw.rectangle([x0, y0, x1, y1], fill=(*rgb, 64), outline=(*rgb, 255), width=3)

        # Budget the label to the box width (with a floor so tiny boxes still show
        # a few characters), but never let it run off the right image edge.
        budget = min(w - x0 - 4, max(x1 - x0, min_label_w))
        label = _truncate(draw, f"{obj.label} {int(obj.confidence * 100)}%", font, budget)
        tx0, ty0, tx1, ty1 = draw.textbbox((0, 0), label, font=font)
        tw, th = tx1 - tx0, ty1 - ty0
        lw, lh = tw + 6, th + 4
        lx = min(x0, w - lw)  # keep the label box within the image

        # Prefer above the box; if that collides or runs off the top, step the
        # label downward (into / below the box top) until it's clear.
        candidates = [y0 - lh] + [y0 + 2 + k * lh for k in range(len(placed) + 2)]
        ly = candidates[0]
        for cy in candidates:
            rect = [lx, cy, lx + lw, cy + lh]
            if cy >= 0 and not any(_intersects(rect, p) for p in placed):
                ly = cy
                break
        ly = max(0, ly)

        rect = [lx, ly, lx + lw, ly + lh]
        placed.append(rect)
        draw.rectangle(rect, fill=(*rgb, 230))
        draw.text((lx + 3, ly + 2), label, fill=(255, 255, 255, 255), font=font)


def _draw_legend(overlay, draw, w, h, font, objects) -> None:
    # Keep the panel readable: cap each line to roughly half the image width.
    line_budget = max(w // 2, 120)
    lines = [
        _truncate(draw, f"{i + 1}. {o.label} {int(o.confidence * 100)}%", font, line_budget)
        for i, o in enumerate(objects)
    ]
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

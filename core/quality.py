"""Image quality pre-check — flag blank or badly blurred images before analysis.

Two cheap, pure-Pillow heuristics let `app.py` warn the user before spending a
Gemini call on an unusable photo:

- **blank**: a full-black / full-white / flat-color frame has near-zero global
  grayscale standard deviation, regardless of the color.
- **blurry**: a soft or featureless image has near-zero variance in its Laplacian
  (edge) response.

Both metrics are computed on a resolution-normalized grayscale copy, and the
Laplacian's 1-pixel convolution border is cropped off before measuring — that
border is a flat-image artifact that otherwise floods the variance. Thresholds
are tuned on the sample desk photos and are heuristic estimates, not guarantees;
the UI treats a flag as a warning the user can override.
"""

from PIL import Image, ImageFilter, ImageStat

_WORK_EDGE = 512  # normalize longest edge so thresholds are resolution-independent
_BLANK_STD_MAX = 8.0  # grayscale std below this → effectively a solid/flat frame
_BLUR_VAR_MIN = 80.0  # Laplacian variance below this → no usable detail (blurred)
_BORDER = 2  # px trimmed from the Laplacian to drop the convolution-edge artifact

_LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)


def check_image_quality(image: Image.Image) -> str | None:
    """Return "blank" or "blurry" if the image looks unusable, else None.

    Pure function, no network calls. "blank" is checked first because a flat
    bright frame can still register a non-trivial edge response at its borders.
    """
    gray = image.convert("L")
    longest = max(gray.size)
    if longest > _WORK_EDGE:
        scale = _WORK_EDGE / longest
        gray = gray.resize(
            (max(1, int(gray.size[0] * scale)), max(1, int(gray.size[1] * scale)))
        )

    if ImageStat.Stat(gray).stddev[0] < _BLANK_STD_MAX:
        return "blank"

    lap = gray.filter(_LAPLACIAN)
    w, h = lap.size
    if w > 2 * _BORDER and h > 2 * _BORDER:
        lap = lap.crop((_BORDER, _BORDER, w - _BORDER, h - _BORDER))
    if ImageStat.Stat(lap).var[0] < _BLUR_VAR_MIN:
        return "blurry"

    return None

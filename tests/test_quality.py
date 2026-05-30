"""Tests for the image quality pre-check (core.quality).

Images are synthesized deterministically so the cases sit far from the
thresholds and don't depend on sample files or RNG.
"""

from PIL import Image, ImageFilter

from core.quality import check_image_quality


def _checkerboard(size=(400, 300), block=20):
    """High-contrast, high-detail image — should read as usable."""
    img = Image.new("L", size)
    px = img.load()
    w, h = size
    for y in range(h):
        for x in range(w):
            px[x, y] = 255 if ((x // block + y // block) % 2 == 0) else 0
    return img


def test_solid_black_is_blank():
    assert check_image_quality(Image.new("RGB", (400, 300), (0, 0, 0))) == "blank"


def test_solid_white_is_blank():
    assert check_image_quality(Image.new("RGB", (400, 300), (255, 255, 255))) == "blank"


def test_flat_color_is_blank():
    assert check_image_quality(Image.new("RGB", (400, 300), (128, 64, 32))) == "blank"


def test_smooth_gradient_is_blurry():
    # High global contrast (not blank) but no fine detail → low Laplacian variance.
    grad = Image.linear_gradient("L").resize((400, 300))
    assert check_image_quality(grad) == "blurry"


def test_high_contrast_but_no_detail_is_blurry():
    # Half black / half white keeps std high (not blank), but its single soft
    # edge carries almost no Laplacian variance → blurry.
    half = Image.new("L", (400, 300), 0)
    half.paste(255, (200, 0, 400, 300))
    assert check_image_quality(half.filter(ImageFilter.GaussianBlur(6))) == "blurry"


def test_sharp_detailed_image_is_usable():
    assert check_image_quality(_checkerboard()) is None

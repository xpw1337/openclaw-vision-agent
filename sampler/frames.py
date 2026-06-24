"""Frame extraction from a recorded clip with OpenCV.

Yields JPEG-encoded frames spaced roughly `interval_seconds` apart in clip time.
On end-of-clip the generator restarts from the beginning when `loop` is set, so
a short recorded clip can drive a continuous demo feed.
"""

from collections.abc import Iterator

import cv2

_DEFAULT_FPS = 25.0


def _encode_jpeg(frame, max_edge: int) -> bytes:
    height, width = frame.shape[:2]
    longest = max(height, width)
    if max_edge and longest > max_edge:
        scale = max_edge / longest
        frame = cv2.resize(frame, (int(width * scale), int(height * scale)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return buf.tobytes()


def iter_frames(
    clip_path: str,
    interval_seconds: float,
    loop: bool,
    max_edge: int,
) -> Iterator[bytes]:
    """Yield JPEG bytes for one frame every `interval_seconds` of clip time."""
    while True:
        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open clip: {clip_path}")
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or _DEFAULT_FPS
            if fps <= 0:
                fps = _DEFAULT_FPS
            step = max(1, int(round(fps * interval_seconds)))
            index = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if index % step == 0:
                    yield _encode_jpeg(frame, max_edge)
                index += 1
        finally:
            cap.release()
        if not loop:
            break

"""Tests for the frame sampler (mocked video capture, mocked NATS)."""

import asyncio
import itertools
import json
from unittest.mock import AsyncMock

import numpy as np
import pytest

import sampler.frames as frames
import sampler.main as sampler_main


class _FakeCapture:
    """Stand-in for cv2.VideoCapture yielding a fixed list of frames once."""

    def __init__(self, frame_list, fps):
        self._frames = frame_list
        self._fps = fps
        self._i = 0

    def isOpened(self):
        return True

    def get(self, _prop):
        return self._fps

    def read(self):
        if self._i < len(self._frames):
            frame = self._frames[self._i]
            self._i += 1
            return True, frame
        return False, None

    def release(self):
        pass


def _frames(n):
    return [np.full((8, 8, 3), i % 256, dtype=np.uint8) for i in range(n)]


def test_iter_frames_samples_on_interval(monkeypatch):
    # fps=10, interval=1s -> every 10th frame; 25 frames -> indices 0,10,20 = 3.
    monkeypatch.setattr(frames.cv2, "VideoCapture", lambda _p: _FakeCapture(_frames(25), 10.0))
    out = list(frames.iter_frames("clip.avi", interval_seconds=1.0, loop=False, max_edge=0))
    assert len(out) == 3
    assert all(jpeg[:2] == b"\xff\xd8" for jpeg in out)


def test_iter_frames_loops(monkeypatch):
    monkeypatch.setattr(frames.cv2, "VideoCapture", lambda _p: _FakeCapture(_frames(12), 10.0))
    # 12 frames, every 10th -> 2 per pass (idx 0, 10). Looping should keep going.
    out = list(itertools.islice(frames.iter_frames("clip.avi", 1.0, True, 0), 5))
    assert len(out) == 5


def test_iter_frames_raises_when_unopenable(monkeypatch):
    class _Closed(_FakeCapture):
        def isOpened(self):
            return False

    monkeypatch.setattr(frames.cv2, "VideoCapture", lambda _p: _Closed([], 10.0))
    with pytest.raises(FileNotFoundError):
        list(frames.iter_frames("missing.avi", 1.0, False, 0))


def test_main_publishes_imagejob_with_camera_and_zone(monkeypatch):
    nc = AsyncMock()

    async def _connect(*_a, **_k):
        return nc

    monkeypatch.setattr(sampler_main.nats, "connect", _connect)
    # Replace the (blocking, cv2-backed) generator with a finite fake.
    monkeypatch.setattr(sampler_main, "iter_frames", lambda *_a, **_k: iter([b"\xff\xd8jpegbytes"]))
    monkeypatch.setenv("CAMERA_ID", "cam-x")
    monkeypatch.setenv("ZONE", "dock")
    monkeypatch.setenv("CLIP_PATH", "clip.avi")
    monkeypatch.setenv("SAMPLE_INTERVAL_SECONDS", "0")

    asyncio.run(sampler_main.run())

    subject, payload = nc.publish.call_args.args
    assert subject == "jobs.images"
    job = json.loads(payload)
    assert job["camera_id"] == "cam-x"
    assert job["zone"] == "dock"
    assert job["image_b64"]  # populated, valid base64 (ImageJob validates it)

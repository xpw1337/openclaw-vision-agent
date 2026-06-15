"""Tests for the worker message handler (mocked NATS, no live API)."""

import asyncio
import base64
import json
from unittest.mock import AsyncMock, patch

import pytest

from agent.config import Settings
from agent.messages import ImageJob
from agent.worker import handle_job
from core.vision import VisionAnalysis

_B64 = base64.b64encode(b"fake image bytes").decode()


class _Msg:
    def __init__(self, data: bytes):
        self.data = data


def _settings():
    return Settings()


def _job_msg():
    job = ImageJob(job_id="j1", camera_id="cam-1", image_b64=_B64)
    return _Msg(job.model_dump_json().encode())


def _published(nc):
    subject, payload = nc.publish.call_args.args
    return subject, json.loads(payload)


def test_handle_job_success():
    analysis = VisionAnalysis(
        scene_summary="a desk",
        objects=[],
        risks_or_opportunities=[],
        suggested_actions=[],
        confidence_notes="",
    )
    nc = AsyncMock()
    with patch("agent.worker.analyze_image", return_value=analysis) as mock_analyze:
        asyncio.run(handle_job(nc, _settings(), _job_msg()))

    mock_analyze.assert_called_once_with(b"fake image bytes")
    subject, obs = _published(nc)
    assert subject == "observations"
    assert obs["job_id"] == "j1"
    assert obs["camera_id"] == "cam-1"
    assert obs["error"] is None
    assert obs["analysis"]["scene_summary"] == "a desk"


def test_handle_job_analysis_failure_publishes_error_observation():
    nc = AsyncMock()
    with patch("agent.worker.analyze_image", side_effect=RuntimeError("api down")):
        asyncio.run(handle_job(nc, _settings(), _job_msg()))

    subject, obs = _published(nc)
    assert subject == "observations"
    assert obs["job_id"] == "j1"
    assert obs["analysis"] is None
    assert "api down" in obs["error"]


def test_handle_job_malformed_message_publishes_error_observation():
    nc = AsyncMock()
    asyncio.run(handle_job(nc, _settings(), _Msg(b"not json at all")))

    subject, obs = _published(nc)
    assert subject == "observations"
    assert obs["job_id"] == "unknown"
    assert obs["error"] == "malformed job message"

"""Tests for the worker message handler (mocked NATS, no live API)."""

import asyncio
import base64
import json
from unittest.mock import AsyncMock, patch

import pytest

from agent.config import Settings
from agent.messages import ImageJob
from agent.worker import handle_jetstream_job, handle_job
from core.vision import VisionAnalysis

_B64 = base64.b64encode(b"fake image bytes").decode()


class _Msg:
    def __init__(self, data: bytes):
        self.data = data
class _JetStreamMsg(_Msg):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.ack = AsyncMock()
        self.nak = AsyncMock()




def _settings():
    return Settings()


def _job_msg(zone="dock"):
    job = ImageJob(job_id="j1", camera_id="cam-1", zone=zone, image_b64=_B64)
    return _Msg(job.model_dump_json().encode())


def _published(nc):
    subject, payload = nc.publish.call_args.args
    return subject, json.loads(payload)


def _published_payloads(nc):
    return [(call.args[0], json.loads(call.args[1])) for call in nc.publish.call_args_list]


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

    mock_analyze.assert_called_once_with(b"fake image bytes", "dock")
    subject, obs = _published(nc)
    assert subject == "observations"
    assert obs["job_id"] == "j1"
    assert obs["camera_id"] == "cam-1"
    assert obs["zone"] == "dock"
    assert obs["error"] is None
    assert obs["job_published_at"] is not None
    assert obs["analysis"]["scene_summary"] == "a desk"


def test_handle_job_analysis_failure_publishes_error_observation():
    nc = AsyncMock()
    with patch("agent.worker.analyze_image", side_effect=RuntimeError("api down")):
        asyncio.run(handle_job(nc, _settings(), _job_msg()))

    published = _published_payloads(nc)
    subject, obs = published[0]
    assert subject == "observations"
    assert obs["job_id"] == "j1"
    assert obs["zone"] == "dock"
    assert obs["analysis"] is None
    assert "api down" in obs["error"]
    dlq_subject, dlq = published[1]
    assert dlq_subject == "jobs.dlq"
    assert dlq["job_id"] == "j1"
    assert dlq["attempts"] == 1


def test_handle_job_malformed_message_publishes_error_observation():
    nc = AsyncMock()
    asyncio.run(handle_job(nc, _settings(), _Msg(b"not json at all")))

    published = _published_payloads(nc)
    subject, obs = published[0]
    assert subject == "observations"
    assert obs["job_id"] == "unknown"
    assert obs["zone"] == "unknown"
    assert obs["error"] == "malformed job message"
    dlq_subject, dlq = published[1]
    assert dlq_subject == "jobs.dlq"
    assert dlq["terminal"] is True


def test_handle_job_retries_transient_failure_then_succeeds():
    analysis = VisionAnalysis(
        scene_summary="a dock",
        objects=[],
        risks_or_opportunities=[],
        suggested_actions=[],
        confidence_notes="",
    )
    nc = AsyncMock()
    sleep = AsyncMock()
    settings = Settings(max_retries=2, retry_base_delay_seconds=0.1)
    with patch("agent.worker.analyze_image", side_effect=[TimeoutError("temporary"), analysis]) as mock_analyze:
        asyncio.run(handle_job(nc, settings, _job_msg(), sleep=sleep))

    assert mock_analyze.call_count == 2
    sleep.assert_awaited_once_with(0.1)
    assert nc.publish.await_count == 1
    subject, obs = _published(nc)
    assert subject == "observations"
    assert obs["error"] is None


def test_jetstream_job_acks_after_handled_message():
    analysis = VisionAnalysis(
        scene_summary="a dock",
        objects=[],
        risks_or_opportunities=[],
        suggested_actions=[],
        confidence_notes="",
    )
    nc = AsyncMock()
    msg = _JetStreamMsg(_job_msg().data)
    with patch("agent.worker.analyze_image", return_value=analysis):
        asyncio.run(handle_jetstream_job(nc, _settings(), msg))

    msg.ack.assert_awaited_once()
    msg.nak.assert_not_awaited()


def test_jetstream_job_naks_when_publish_fails():
    analysis = VisionAnalysis(
        scene_summary="a dock",
        objects=[],
        risks_or_opportunities=[],
        suggested_actions=[],
        confidence_notes="",
    )
    nc = AsyncMock()
    nc.publish.side_effect = RuntimeError("nats down")
    msg = _JetStreamMsg(_job_msg().data)
    with patch("agent.worker.analyze_image", return_value=analysis):
        asyncio.run(handle_jetstream_job(nc, _settings(), msg))

    msg.ack.assert_not_awaited()
    msg.nak.assert_awaited_once()

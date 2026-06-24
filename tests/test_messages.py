"""Tests for the agent wire schema (ImageJob / Observation)."""

import base64
import json

import pytest
from pydantic import ValidationError

from agent.messages import ImageJob, Observation, SCHEMA_VERSION
from core.vision import DetectedObject, VisionAnalysis

_B64 = base64.b64encode(b"fake image bytes").decode()


def _analysis():
    return VisionAnalysis(
        scene_summary="a desk",
        objects=[DetectedObject(label="laptop", confidence=0.95, bbox=[0.1, 0.2, 0.3, 0.4])],
        risks_or_opportunities=["cable near edge"],
        suggested_actions=["move the cable"],
        confidence_notes="clear image",
    )


def test_image_job_round_trip():
    job = ImageJob(job_id="j1", camera_id="cam-1", zone="dock", image_b64=_B64)
    restored = ImageJob.model_validate_json(job.model_dump_json())
    assert restored.job_id == "j1"
    assert restored.camera_id == "cam-1"
    assert restored.zone == "dock"
    assert restored.image_bytes() == b"fake image bytes"
    assert restored.timestamp == job.timestamp


def test_zone_defaults_to_unknown():
    job = ImageJob(job_id="j1", camera_id="cam-1", image_b64=_B64)
    assert job.zone == "unknown"
    obs = Observation(job_id="j1", camera_id="cam-1", worker_id="w1")
    assert obs.zone == "unknown"


def test_schema_version_is_0_2():
    assert SCHEMA_VERSION == "0.2"
    assert Observation(job_id="j1", camera_id="cam-1", worker_id="w1").schema_version == "0.2"


def test_image_job_rejects_invalid_base64():
    with pytest.raises(ValidationError):
        ImageJob(job_id="j1", camera_id="cam-1", image_b64="not!!valid$$base64")


def test_image_job_rejects_missing_fields():
    with pytest.raises(ValidationError):
        ImageJob.model_validate_json(json.dumps({"job_id": "j1"}))


def test_observation_round_trip_with_analysis():
    obs = Observation(
        job_id="j1", camera_id="cam-1", zone="lobby", worker_id="w1", analysis=_analysis()
    )
    restored = Observation.model_validate_json(obs.model_dump_json())
    assert restored.schema_version == SCHEMA_VERSION
    assert restored.zone == "lobby"
    assert restored.error is None
    assert restored.analysis.objects[0].label == "laptop"
    assert restored.analysis.objects[0].bbox == pytest.approx([0.1, 0.2, 0.3, 0.4])


def test_observation_error_path():
    obs = Observation(job_id="j1", camera_id="cam-1", worker_id="w1", error="boom")
    restored = Observation.model_validate_json(obs.model_dump_json())
    assert restored.analysis is None
    assert restored.error == "boom"

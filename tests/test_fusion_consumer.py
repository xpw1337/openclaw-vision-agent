"""Tests for the fusion consumer: persist valid observations, reject malformed."""

import asyncio
from unittest.mock import AsyncMock

from agent.messages import Observation
from core.vision import VisionAnalysis
from fusion.consumer import process


def _valid_obs_bytes():
    obs = Observation(
        job_id="j1",
        camera_id="cam-1",
        zone="dock",
        worker_id="w1",
        analysis=VisionAnalysis(
            scene_summary="x",
            objects=[],
            risks_or_opportunities=[],
            suggested_actions=[],
            confidence_notes="",
        ),
    )
    return obs.model_dump_json().encode()


def test_process_persists_valid_observation():
    db = AsyncMock()
    store = AsyncMock()
    result = asyncio.run(process(db, store, _valid_obs_bytes()))
    assert result is True
    db.insert_observation.assert_awaited_once()
    store.update_snapshot.assert_awaited_once()


def test_process_rejects_malformed_message():
    db = AsyncMock()
    store = AsyncMock()
    result = asyncio.run(process(db, store, b"not valid json"))
    assert result is False
    db.insert_observation.assert_not_called()
    store.update_snapshot.assert_not_called()


def test_process_returns_false_when_persistence_fails():
    db = AsyncMock()
    db.insert_observation.side_effect = RuntimeError("db down")
    store = AsyncMock()
    result = asyncio.run(process(db, store, _valid_obs_bytes()))
    assert result is False

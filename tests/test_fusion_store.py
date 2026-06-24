"""Tests for the Redis snapshot store and per-zone fusion (fakeredis)."""

import asyncio

import fakeredis.aioredis

from agent.messages import Observation
from core.vision import DetectedObject, VisionAnalysis
from fusion.store import Store, summarize_zone


def _obs(camera, zone, labels, risks=None):
    return Observation(
        job_id=f"job-{camera}",
        camera_id=camera,
        zone=zone,
        worker_id="w1",
        analysis=VisionAnalysis(
            scene_summary="x",
            objects=[DetectedObject(label=label, confidence=0.9) for label in labels],
            risks_or_opportunities=risks or [],
            suggested_actions=[],
            confidence_notes="",
        ),
    )


def _store():
    return Store.from_client(fakeredis.aioredis.FakeRedis(decode_responses=True))


def test_summarize_zone_counts_objects_and_dedupes_risks():
    summary = summarize_zone(
        "dock",
        [
            _obs("cam-dock-1", "dock", ["person", "person"], ["spill detected"]).model_dump(mode="json"),
            _obs("cam-dock-2", "dock", ["forklift"], ["spill detected"]).model_dump(mode="json"),
        ],
    )
    assert summary["camera_count"] == 2
    assert summary["object_counts"] == {"person": 2, "forklift": 1}
    assert summary["risks"] == ["spill detected"]
    assert "dock" in summary["summary"]


def test_quiet_zone_summary():
    summary = summarize_zone("lobby", [_obs("cam-lobby-1", "lobby", []).model_dump(mode="json")])
    assert summary["camera_count"] == 1
    assert summary["object_counts"] == {}
    assert "quiet" in summary["summary"]


def test_update_and_get_area_across_zones():
    async def _run():
        store = _store()
        await store.update_snapshot(_obs("cam-dock-1", "dock", ["person", "person"]))
        await store.update_snapshot(_obs("cam-dock-2", "dock", ["forklift"], ["spill detected"]))
        await store.update_snapshot(_obs("cam-lobby-1", "lobby", []))
        return await store.list_zones(), await store.get_zone("dock"), await store.get_area()

    zones, dock, area = asyncio.run(_run())
    assert zones == ["dock", "lobby"]
    assert dock["camera_count"] == 2
    assert dock["object_counts"] == {"person": 2, "forklift": 1}
    assert dock["risks"] == ["spill detected"]
    assert {z["zone"] for z in area["zones"]} == {"dock", "lobby"}


def test_latest_observation_per_camera_overwrites():
    async def _run():
        store = _store()
        await store.update_snapshot(_obs("cam-dock-1", "dock", ["person", "person", "person"]))
        # Same camera reports again — should replace, not accumulate.
        await store.update_snapshot(_obs("cam-dock-1", "dock", ["forklift"]))
        return await store.get_zone("dock")

    dock = asyncio.run(_run())
    assert dock["camera_count"] == 1
    assert dock["object_counts"] == {"forklift": 1}

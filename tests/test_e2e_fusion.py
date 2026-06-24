"""End-to-end fusion path (no cluster): observation bytes -> consumer -> Redis -> GET /area.

Exercises the real Observation validation, the real Redis-backed Store (via
fakeredis), and the real FastAPI router in a single event loop. Postgres is
represented by an AsyncMock so we can assert what would be persisted without a
live database. This mirrors the Week 2 acceptance criteria.
"""

import asyncio
from unittest.mock import AsyncMock

import fakeredis.aioredis
import httpx
from fastapi import FastAPI

from agent.messages import Observation
from core.vision import DetectedObject, VisionAnalysis
from fusion.api import get_store, router
from fusion.consumer import process
from fusion.store import Store


def _obs_bytes(camera, zone, labels, risks=None):
    obs = Observation(
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
    return obs.model_dump_json().encode()


def test_observations_flow_into_fused_area_summary():
    async def _run():
        store = Store.from_client(fakeredis.aioredis.FakeRedis(decode_responses=True))
        db = AsyncMock()

        # Multiple cameras report; dock has two, lobby has one.
        assert await process(db, store, _obs_bytes("cam-dock-1", "dock", ["person", "person"]))
        assert await process(db, store, _obs_bytes("cam-dock-2", "dock", ["forklift"], ["spill detected"]))
        assert await process(db, store, _obs_bytes("cam-lobby-1", "lobby", []))
        # A malformed observation is rejected (schema validation gate).
        assert not await process(db, store, b"{ not json")

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_store] = lambda: store
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            area = (await client.get("/area")).json()
        return db, area

    db, area = asyncio.run(_run())

    # Only the three valid observations would land in Postgres.
    assert db.insert_observation.await_count == 3

    zones = {z["zone"]: z for z in area["zones"]}
    assert set(zones) == {"dock", "lobby"}
    # Dock fuses two cameras into one zone view.
    assert zones["dock"]["camera_count"] == 2
    assert zones["dock"]["object_counts"] == {"person": 2, "forklift": 1}
    assert "spill detected" in zones["dock"]["risks"]
    # Lobby is quiet.
    assert "quiet" in zones["lobby"]["summary"]

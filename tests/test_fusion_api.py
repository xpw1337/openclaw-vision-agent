"""Tests for the fusion read API (FastAPI TestClient, mocked store, no lifespan)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fusion.api import get_store, router


class _FakeStore:
    async def list_zones(self):
        return ["dock", "lobby"]

    async def get_zone(self, zone):
        return {"zone": zone, "camera_count": 1, "summary": f"{zone}: quiet"}

    async def get_area(self):
        return {"zones": [await self.get_zone("dock"), await self.get_zone("lobby")]}


def _client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_store] = lambda: _FakeStore()
    return TestClient(app)


def test_healthz():
    assert _client().get("/healthz").json() == {"status": "ok"}


def test_zones():
    assert _client().get("/zones").json() == {"zones": ["dock", "lobby"]}


def test_area_returns_all_zones():
    body = _client().get("/area").json()
    assert {z["zone"] for z in body["zones"]} == {"dock", "lobby"}


def test_zone_lookup():
    body = _client().get("/zone/dock").json()
    assert body["zone"] == "dock"


def test_unknown_zone_404():
    resp = _client().get("/zone/nope")
    assert resp.status_code == 404

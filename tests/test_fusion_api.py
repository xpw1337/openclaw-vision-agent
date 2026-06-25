"""Tests for the fusion read API (FastAPI TestClient, mocked store, no lifespan)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fusion.api import get_store, router


class _FakeStore:
    async def list_zones(self):
        return ["dock", "lobby"]

    async def get_zone(self, zone):
        return {
            "zone": zone,
            "camera_count": 1,
            "stale_camera_count": 0,
            "summary": f"{zone}: quiet",
            "cameras_detail": [
                {
                    "camera_id": f"cam-{zone}-1",
                    "zone": zone,
                    "stale": False,
                    "error": None,
                    "object_counts": {},
                    "risks": [],
                }
            ],
        }

    async def get_area(self):
        zones = [await self.get_zone("dock"), await self.get_zone("lobby")]
        return {"as_of": "now", "camera_total": 2, "stale_camera_count": 0, "zones": zones}


def _client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_store] = lambda: _FakeStore()
    return TestClient(app)


def test_healthz():
    assert _client().get("/healthz").json() == {"status": "ok"}


def test_dashboard_root_serves_html():
    resp = _client().get("/")
    assert resp.status_code == 200
    assert "Area Awareness Dashboard" in resp.text


def test_zones():
    assert _client().get("/zones").json() == {"zones": ["dock", "lobby"]}


def test_area_returns_all_zones():
    body = _client().get("/area").json()
    assert {z["zone"] for z in body["zones"]} == {"dock", "lobby"}
    assert body["camera_total"] == 2
    assert body["stale_camera_count"] == 0
    assert body["zones"][0]["cameras_detail"][0]["error"] is None


def test_zone_lookup():
    body = _client().get("/zone/dock").json()
    assert body["zone"] == "dock"


def test_unknown_zone_404():
    resp = _client().get("/zone/nope")
    assert resp.status_code == 404

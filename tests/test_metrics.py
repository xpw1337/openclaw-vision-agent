"""Smoke tests for Prometheus metrics endpoints."""

from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.health import start_health_server
from fusion.api import get_store, router


class _FakeStore:
    async def list_zones(self):
        return []

    async def get_area(self):
        return {"as_of": "now", "camera_total": 0, "stale_camera_count": 0, "zones": []}


def test_worker_health_server_exposes_metrics():
    server = start_health_server(0, ready_check=lambda: True)
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/metrics", timeout=2) as resp:
            body = resp.read().decode()
    finally:
        server.shutdown()

    assert resp.status == 200
    assert "python_info" in body


def test_fusion_api_exposes_metrics():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_store] = lambda: _FakeStore()

    resp = TestClient(app).get("/metrics")

    assert resp.status_code == 200
    assert "python_info" in resp.text

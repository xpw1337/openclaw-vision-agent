"""Redis live snapshot of the current per-zone area state.

For each zone we keep the latest observation per camera in a hash
(`zone:{zone}` -> {camera_id: observation_json}). Reads aggregate those into a
fused per-zone summary; the whole-area view is the union across zones.
"""

import json

import redis.asyncio as aioredis

from agent.messages import Observation

_ZONES_KEY = "zones"


def _zone_key(zone: str) -> str:
    return f"zone:{zone}"


def _text_summary(zone: str, cameras: list[str], object_counts: dict[str, int], risks: list[str]) -> str:
    cam_part = f"{len(cameras)} camera" + ("s" if len(cameras) != 1 else "")
    if object_counts:
        objs = ", ".join(f"{count} {label}" for label, count in sorted(object_counts.items()))
    else:
        objs = "quiet, nothing notable"
    text = f"{zone}: {cam_part}, {objs}"
    if risks:
        text += f"; risks: {', '.join(risks)}"
    return text


def summarize_zone(zone: str, observations: list[dict]) -> dict:
    """Fuse the latest observation per camera into one zone summary."""
    cameras = sorted({o.get("camera_id", "unknown") for o in observations})
    object_counts: dict[str, int] = {}
    risks: list[str] = []
    last_updated: str | None = None

    for obs in observations:
        ts = obs.get("timestamp")
        if ts and (last_updated is None or ts > last_updated):
            last_updated = ts
        analysis = obs.get("analysis")
        if not analysis:
            continue
        for obj in analysis.get("objects", []):
            label = obj.get("label", "unknown")
            object_counts[label] = object_counts.get(label, 0) + 1
        for risk in analysis.get("risks_or_opportunities", []):
            if risk not in risks:
                risks.append(risk)

    return {
        "zone": zone,
        "camera_count": len(cameras),
        "cameras": cameras,
        "object_counts": object_counts,
        "risks": risks,
        "last_updated": last_updated,
        "summary": _text_summary(zone, cameras, object_counts, risks),
    }


class Store:
    """Redis-backed live snapshot."""

    def __init__(self, url: str):
        self._url = url
        self._redis: aioredis.Redis | None = None

    @classmethod
    def from_client(cls, client: aioredis.Redis) -> "Store":
        """Build a Store around an existing client (used in tests with fakeredis)."""
        store = cls.__new__(cls)
        store._url = ""
        store._redis = client
        return store

    async def connect(self) -> None:
        self._redis = aioredis.from_url(self._url, decode_responses=True)
        await self._redis.ping()

    async def update_snapshot(self, obs: Observation) -> None:
        await self._redis.hset(_zone_key(obs.zone), obs.camera_id, obs.model_dump_json())
        await self._redis.sadd(_ZONES_KEY, obs.zone)

    async def list_zones(self) -> list[str]:
        zones = await self._redis.smembers(_ZONES_KEY)
        return sorted(zones)

    async def get_zone(self, zone: str) -> dict:
        cameras = await self._redis.hgetall(_zone_key(zone))
        observations = [json.loads(v) for v in cameras.values()]
        return summarize_zone(zone, observations)

    async def get_area(self) -> dict:
        zones = await self.list_zones()
        return {"zones": [await self.get_zone(zone) for zone in zones]}

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()

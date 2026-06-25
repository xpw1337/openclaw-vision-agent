"""Redis live snapshot of the current per-zone area state.

For each zone we keep the latest observation per camera in a hash
(`zone:{zone}` -> {camera_id: observation_json}). Reads aggregate those into a
fused per-zone summary; the whole-area view is the union across zones.
"""

import json
from datetime import datetime, timezone

import redis.asyncio as aioredis

from agent.messages import Observation

_ZONES_KEY = "zones"
_DEFAULT_STALE_AFTER_SECONDS = 15.0


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


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _seconds_since(ts: datetime | None, now: datetime) -> float | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (now - ts).total_seconds())


def _object_counts(analysis: dict | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not analysis:
        return counts
    for obj in analysis.get("objects", []):
        label = obj.get("label", "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


def _risks(analysis: dict | None) -> list[str]:
    risks: list[str] = []
    if not analysis:
        return risks
    for risk in analysis.get("risks_or_opportunities", []):
        if risk not in risks:
            risks.append(risk)
    return risks


def _camera_detail(obs: dict, now: datetime, stale_after_seconds: float) -> dict:
    analysis = obs.get("analysis")
    ts = obs.get("timestamp")
    parsed_ts = _parse_timestamp(ts)
    age_seconds = _seconds_since(parsed_ts, now)
    risks = _risks(analysis)
    return {
        "camera_id": obs.get("camera_id", "unknown"),
        "zone": obs.get("zone", "unknown"),
        "last_updated": ts,
        "age_seconds": age_seconds,
        "stale": age_seconds is None or age_seconds > stale_after_seconds,
        "error": obs.get("error"),
        "scene_summary": analysis.get("scene_summary") if analysis else None,
        "object_counts": _object_counts(analysis),
        "risks": risks,
        "suggested_actions": analysis.get("suggested_actions", []) if analysis else [],
    }


def summarize_zone(
    zone: str,
    observations: list[dict],
    *,
    now: datetime | None = None,
    stale_after_seconds: float = _DEFAULT_STALE_AFTER_SECONDS,
) -> dict:
    """Fuse the latest observation per camera into one zone summary."""
    now = now or datetime.now(timezone.utc)
    cameras = sorted({o.get("camera_id", "unknown") for o in observations})
    object_counts: dict[str, int] = {}
    risks: list[str] = []
    last_updated: str | None = None
    camera_details: list[dict] = []

    for obs in observations:
        ts = obs.get("timestamp")
        if ts and (last_updated is None or ts > last_updated):
            last_updated = ts
        analysis = obs.get("analysis")
        camera_details.append(_camera_detail(obs, now, stale_after_seconds))
        for label, count in _object_counts(analysis).items():
            object_counts[label] = object_counts.get(label, 0) + count
        for risk in _risks(analysis):
            if risk not in risks:
                risks.append(risk)

    return {
        "zone": zone,
        "camera_count": len(cameras),
        "cameras": cameras,
        "cameras_detail": sorted(camera_details, key=lambda c: c["camera_id"]),
        "object_counts": object_counts,
        "risks": risks,
        "last_updated": last_updated,
        "stale_camera_count": sum(1 for camera in camera_details if camera["stale"]),
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
        summaries = [await self.get_zone(zone) for zone in zones]
        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "camera_total": sum(zone["camera_count"] for zone in summaries),
            "stale_camera_count": sum(zone["stale_camera_count"] for zone in summaries),
            "zones": summaries,
        }

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()

"""Postgres history store for observations (asyncpg).

Keeps the full append-only history. The schema is created on startup
(idempotent) so no separate migration job is needed for the demo.
"""

import json

import asyncpg

from agent.messages import Observation

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id bigserial PRIMARY KEY,
    job_id text NOT NULL,
    camera_id text NOT NULL,
    zone text NOT NULL,
    worker_id text,
    ts timestamptz NOT NULL,
    scene_summary text,
    objects jsonb NOT NULL DEFAULT '[]'::jsonb,
    risks jsonb NOT NULL DEFAULT '[]'::jsonb,
    suggested_actions jsonb NOT NULL DEFAULT '[]'::jsonb,
    confidence_notes text,
    schema_version text,
    error text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS observations_zone_idx ON observations (zone);
CREATE INDEX IF NOT EXISTS observations_ts_idx ON observations (ts);
"""

_INSERT = """
INSERT INTO observations
    (job_id, camera_id, zone, worker_id, ts, scene_summary,
     objects, risks, suggested_actions, confidence_notes, schema_version, error)
VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9::jsonb, $10, $11, $12)
"""


class Database:
    """Thin asyncpg wrapper holding a connection pool."""

    def __init__(self, dsn: str, password: str | None = None):
        self._dsn = dsn
        self._password = password
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn, password=self._password, min_size=1, max_size=5
        )
        await self.ensure_schema()

    async def ensure_schema(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA)

    async def insert_observation(self, obs: Observation) -> None:
        analysis = obs.analysis
        objects = [o.model_dump() for o in analysis.objects] if analysis else []
        risks = analysis.risks_or_opportunities if analysis else []
        actions = analysis.suggested_actions if analysis else []
        scene = analysis.scene_summary if analysis else None
        notes = analysis.confidence_notes if analysis else None

        async with self._pool.acquire() as conn:
            await conn.execute(
                _INSERT,
                obs.job_id,
                obs.camera_id,
                obs.zone,
                obs.worker_id,
                obs.timestamp,
                scene,
                json.dumps(objects),
                json.dumps(risks),
                json.dumps(actions),
                notes,
                obs.schema_version,
                obs.error,
            )

    async def count(self, zone: str | None = None) -> int:
        async with self._pool.acquire() as conn:
            if zone is None:
                return await conn.fetchval("SELECT count(*) FROM observations")
            return await conn.fetchval(
                "SELECT count(*) FROM observations WHERE zone = $1", zone
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

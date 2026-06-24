"""NATS consumer: observations -> Postgres history + Redis snapshot.

Malformed messages are rejected (logged and dropped) so a bad publisher can't
corrupt the fused state — this is the schema-validation gate for the pipeline.
"""

import logging

from agent.messages import Observation
from fusion.db import Database
from fusion.store import Store

logger = logging.getLogger("fusion.consumer")


async def process(db: Database, store: Store, raw: bytes) -> bool:
    """Validate, persist, and snapshot one observation. Returns False if rejected."""
    try:
        obs = Observation.model_validate_json(raw)
    except Exception:
        logger.warning("Rejected malformed observation (%d bytes)", len(raw))
        return False

    try:
        await db.insert_observation(obs)
        await store.update_snapshot(obs)
    except Exception:
        logger.exception("Failed to persist observation %s", obs.job_id)
        return False

    logger.info("Fused observation %s (camera %s, zone %s)", obs.job_id, obs.camera_id, obs.zone)
    return True


class Consumer:
    """Subscribes to the observations subject and fuses each message."""

    def __init__(self, nc, subject: str, db: Database, store: Store):
        self._nc = nc
        self._subject = subject
        self._db = db
        self._store = store
        self._sub = None

    async def start(self) -> None:
        self._sub = await self._nc.subscribe(self._subject, cb=self._on_message)
        logger.info("Subscribed to %s", self._subject)

    async def _on_message(self, msg) -> None:
        await process(self._db, self._store, msg.data)

    async def stop(self) -> None:
        if self._sub is not None:
            await self._sub.unsubscribe()

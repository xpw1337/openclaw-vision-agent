"""Wire models for the NATS subjects (v0 of the shared observation schema).

JSON on the wire, Pydantic at the edges: jobs arrive on `jobs.images` as
`ImageJob`, results go out on `observations` as `Observation`. The Observation
embeds the existing `VisionAnalysis` so Week 2's fusion service can consume the
same structured output the Streamlit app already uses.
"""

import base64
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from core.vision import VisionAnalysis

SCHEMA_VERSION = "0.3"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImageJob(BaseModel):
    job_id: str
    camera_id: str
    zone: str = "unknown"
    image_b64: str
    timestamp: datetime = Field(default_factory=_utcnow)

    @field_validator("image_b64")
    @classmethod
    def _valid_base64(cls, v: str) -> str:
        try:
            base64.b64decode(v, validate=True)
        except Exception as exc:
            raise ValueError("image_b64 is not valid base64") from exc
        return v

    def image_bytes(self) -> bytes:
        return base64.b64decode(self.image_b64)


class Observation(BaseModel):
    schema_version: str = SCHEMA_VERSION
    job_id: str
    camera_id: str
    zone: str = "unknown"
    worker_id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    job_published_at: datetime | None = None
    analysis: VisionAnalysis | None = None
    error: str | None = None


class DeadLetterJob(BaseModel):
    schema_version: str = SCHEMA_VERSION
    job_id: str
    camera_id: str
    zone: str = "unknown"
    worker_id: str
    failed_at: datetime = Field(default_factory=_utcnow)
    attempts: int = 1
    reason: str
    terminal: bool = False
    job_published_at: datetime | None = None

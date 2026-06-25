"""Sampler settings, sourced exclusively from environment variables.

One sampler process represents one camera: it owns a recorded clip, samples a
frame on an interval, and publishes ImageJobs (tagged with camera_id + zone) to
the jobs subject the Week 1 worker pool already consumes.
"""

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    nats_url: str = field(default_factory=lambda: os.getenv("NATS_URL", "nats://localhost:4222"))
    jobs_subject: str = field(default_factory=lambda: os.getenv("JOBS_SUBJECT", "jobs.images"))
    camera_id: str = field(default_factory=lambda: os.getenv("CAMERA_ID", "cam-local"))
    zone: str = field(default_factory=lambda: os.getenv("ZONE", "unknown"))
    clip_path: str = field(default_factory=lambda: os.getenv("CLIP_PATH", ""))
    sample_interval_seconds: float = field(
        default_factory=lambda: _env_float("SAMPLE_INTERVAL_SECONDS", 5.0)
    )
    loop: bool = field(default_factory=lambda: _env_bool("LOOP", True))
    # Longest-edge cap for the JPEG sent on the wire (keeps NATS payloads small;
    # the model preprocessor downscales again to 2048 anyway).
    max_image_size: int = field(default_factory=lambda: _env_int("MAX_IMAGE_SIZE", 1280))
    jetstream_enabled: bool = field(default_factory=lambda: _env_bool("JETSTREAM_ENABLED", False))
    metrics_port: int = field(default_factory=lambda: _env_int("METRICS_PORT", 9102))


def load_settings() -> Settings:
    return Settings()

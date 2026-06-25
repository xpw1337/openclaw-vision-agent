"""Worker settings, sourced exclusively from environment variables.

The worker is configured purely by env vars so the same container image can be
deployed as N replicas with a ConfigMap (tuning) + Secret (GEMINI_API_KEY).
"""

import os
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    nats_url: str = field(default_factory=lambda: os.getenv("NATS_URL", "nats://localhost:4222"))
    jobs_subject: str = field(default_factory=lambda: os.getenv("JOBS_SUBJECT", "jobs.images"))
    obs_subject: str = field(default_factory=lambda: os.getenv("OBS_SUBJECT", "observations"))
    queue_group: str = field(default_factory=lambda: os.getenv("QUEUE_GROUP", "workers"))
    health_port: int = field(default_factory=lambda: _env_int("HEALTH_PORT", 8080))
    # Informational identity for published observations; defaults to the pod
    # hostname under Kubernetes.
    worker_id: str = field(default_factory=lambda: os.getenv("WORKER_ID", os.getenv("HOSTNAME", "worker-local")))
    max_retries: int = field(default_factory=lambda: _env_int("MAX_RETRIES", 2))
    retry_base_delay_seconds: float = field(default_factory=lambda: _env_float("RETRY_BASE_DELAY_SECONDS", 1.0))
    retry_max_delay_seconds: float = field(default_factory=lambda: _env_float("RETRY_MAX_DELAY_SECONDS", 15.0))
    dlq_subject: str = field(default_factory=lambda: os.getenv("DLQ_SUBJECT", "jobs.dlq"))
    jetstream_enabled: bool = field(default_factory=lambda: _env_bool("JETSTREAM_ENABLED", False))
    jobs_stream: str = field(default_factory=lambda: os.getenv("JOBS_STREAM", "JOBS"))
    jobs_consumer: str = field(default_factory=lambda: os.getenv("JOBS_CONSUMER", os.getenv("QUEUE_GROUP", "workers")))


def load_settings() -> Settings:
    return Settings()

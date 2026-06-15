"""Worker settings, sourced exclusively from environment variables.

The worker is configured purely by env vars so the same container image can be
deployed as N replicas with a ConfigMap (tuning) + Secret (GEMINI_API_KEY).
"""

import os
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


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


def load_settings() -> Settings:
    return Settings()

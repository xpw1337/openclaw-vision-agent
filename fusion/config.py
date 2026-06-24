"""Fusion service settings, sourced exclusively from environment variables.

The Postgres password is kept separate (`DB_PASSWORD`, from a Kubernetes Secret)
so `DATABASE_URL` can live in a ConfigMap without embedding a credential.
"""

import os
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/surveillance"
        )
    )
    # Optional credential override; when set it takes precedence over any password
    # embedded in DATABASE_URL (keeps secrets out of the ConfigMap).
    db_password: str | None = field(default_factory=lambda: os.getenv("DB_PASSWORD") or None)
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    nats_url: str = field(default_factory=lambda: os.getenv("NATS_URL", "nats://localhost:4222"))
    obs_subject: str = field(default_factory=lambda: os.getenv("OBS_SUBJECT", "observations"))
    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: _env_int("API_PORT", 8000))


def load_settings() -> Settings:
    return Settings()

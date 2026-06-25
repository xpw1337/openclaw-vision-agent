"""Prometheus metrics for frame samplers."""

from prometheus_client import Counter

JOBS_PUBLISHED = Counter(
    "vision_sampler_jobs_published_total",
    "Image jobs published by samplers.",
    ["camera_id", "zone", "transport"],
)

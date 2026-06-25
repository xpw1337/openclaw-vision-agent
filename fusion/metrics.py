"""Prometheus metrics for the fusion service."""

from prometheus_client import Counter

OBSERVATIONS_FUSED = Counter(
    "vision_observations_fused_total",
    "Validated observations persisted and written to the live snapshot.",
    ["zone", "has_error"],
)
OBSERVATIONS_REJECTED = Counter(
    "vision_observations_rejected_total",
    "Observations rejected before reaching the live snapshot.",
    ["reason"],
)

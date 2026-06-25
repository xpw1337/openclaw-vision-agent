"""Prometheus metrics for the vision worker."""

from prometheus_client import Counter, Histogram

JOBS_PROCESSED = Counter(
    "vision_jobs_processed_total",
    "Jobs handled by vision workers.",
    ["result"],
)
JOBS_RETRIED = Counter(
    "vision_jobs_retried_total",
    "Retry attempts scheduled by vision workers.",
)
DLQ_MESSAGES = Counter(
    "vision_dlq_messages_total",
    "Dead-letter messages published by vision workers.",
    ["terminal"],
)
ANALYZE_DURATION = Histogram(
    "vision_analyze_duration_seconds",
    "Wall-clock time spent analyzing one job, including worker-local retries.",
)

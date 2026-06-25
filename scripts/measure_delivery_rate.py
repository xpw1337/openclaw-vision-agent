"""Compute Week 3 delivery-rate summary from observed or expected counts."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DeliveryReport:
    published: int
    processed: int
    succeeded: int
    failed: int
    dlq: int
    delivery_rate: float
    success_rate: float
    failure_rate: float


def expected_published(feeds: int, interval_seconds: float, duration_seconds: float) -> int:
    if feeds < 0 or interval_seconds <= 0 or duration_seconds < 0:
        raise ValueError("feeds and duration must be non-negative; interval must be positive")
    return int(feeds * duration_seconds / interval_seconds)


def compute_report(*, published: int, processed: int, succeeded: int, failed: int, dlq: int = 0) -> DeliveryReport:
    if min(published, processed, succeeded, failed, dlq) < 0:
        raise ValueError("counts must be non-negative")
    denominator = published or 1
    return DeliveryReport(
        published=published,
        processed=processed,
        succeeded=succeeded,
        failed=failed,
        dlq=dlq,
        delivery_rate=processed / denominator,
        success_rate=succeeded / denominator,
        failure_rate=failed / denominator,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--published", type=int, help="Observed jobs published.")
    parser.add_argument("--processed", type=int, required=True, help="Observed jobs processed by workers.")
    parser.add_argument("--succeeded", type=int, required=True, help="Observed successful observations.")
    parser.add_argument("--failed", type=int, required=True, help="Observed failed/error observations.")
    parser.add_argument("--dlq", type=int, default=0, help="Observed DLQ messages.")
    parser.add_argument("--feeds", type=int, help="Feed count for expected published jobs.")
    parser.add_argument("--interval-seconds", type=float, default=5.0, help="Sampler interval.")
    parser.add_argument("--duration-seconds", type=float, default=3600.0, help="Measurement window.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    published = args.published
    if published is None:
        if args.feeds is None:
            raise SystemExit("provide --published or --feeds")
        published = expected_published(args.feeds, args.interval_seconds, args.duration_seconds)

    report = compute_report(
        published=published,
        processed=args.processed,
        succeeded=args.succeeded,
        failed=args.failed,
        dlq=args.dlq,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

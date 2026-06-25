"""Create the minimal JetStream streams used by Week 3.

Run this after NATS is installed and before enabling sampler publishers.
"""

from __future__ import annotations

import asyncio
import os

import nats
from nats.js.api import RetentionPolicy, StorageType, StreamConfig
from nats.js.errors import NotFoundError


async def ensure_stream(js, config: StreamConfig) -> None:
    try:
        await js.stream_info(config.name)
    except NotFoundError:
        await js.add_stream(config)
        print(f"created stream {config.name}: {', '.join(config.subjects)}")
        return
    await js.update_stream(config)
    print(f"updated stream {config.name}: {', '.join(config.subjects)}")


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    jobs_subject = os.getenv("JOBS_SUBJECT", "jobs.images")
    dlq_subject = os.getenv("DLQ_SUBJECT", "jobs.dlq")
    jobs_stream = os.getenv("JOBS_STREAM", "JOBS")
    dlq_stream = os.getenv("DLQ_STREAM", "JOBS_DLQ")

    nc = await nats.connect(nats_url)
    js = nc.jetstream()
    try:
        await ensure_stream(
            js,
            StreamConfig(
                name=jobs_stream,
                subjects=[jobs_subject],
                retention=RetentionPolicy.WORK_QUEUE,
                storage=StorageType.FILE,
                max_msgs=10000,
            ),
        )
        await ensure_stream(
            js,
            StreamConfig(
                name=dlq_stream,
                subjects=[dlq_subject],
                retention=RetentionPolicy.LIMITS,
                storage=StorageType.FILE,
                max_msgs=10000,
            ),
        )
    finally:
        await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())

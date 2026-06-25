"""Sampler entrypoint: clip frames -> jobs.images.

Connects to NATS, samples one frame at a time from the configured clip, wraps it
as an ImageJob (camera_id + zone), and publishes it on the jobs subject. The
Week 1 worker pool picks the job up, analyzes it, and publishes an Observation.
"""

import asyncio
import base64
import logging
import signal
import uuid

import nats
from prometheus_client import start_http_server

from agent.messages import ImageJob
from sampler.config import Settings, load_settings
from sampler.frames import iter_frames
from sampler.metrics import JOBS_PUBLISHED

logger = logging.getLogger("sampler.main")


async def _sleep_or_stop(stop: asyncio.Event, timeout: float) -> None:
    """Sleep up to `timeout` seconds, returning early if shutdown is requested."""
    try:
        await asyncio.wait_for(stop.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass


async def run() -> None:
    settings = load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if not settings.clip_path:
        raise SystemExit("CLIP_PATH is required")
    start_http_server(settings.metrics_port)
    logger.info("Metrics server on :%s (/metrics)", settings.metrics_port)

    nc = await nats.connect(
        settings.nats_url,
        max_reconnect_attempts=-1,
        reconnect_time_wait=2,
    )
    logger.info(
        "Connected to NATS at %s as camera %s (zone %s)",
        settings.nats_url,
        settings.camera_id,
        settings.zone,
    )
    js = nc.jetstream() if settings.jetstream_enabled else None

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: stop.set())

    frames = iter_frames(
        settings.clip_path,
        settings.sample_interval_seconds,
        settings.loop,
        settings.max_image_size,
    )

    published = 0
    while not stop.is_set():
        jpeg = await asyncio.to_thread(next, frames, None)
        if jpeg is None:
            logger.info("Clip exhausted (loop disabled); sampler done")
            break

        job = ImageJob(
            job_id=uuid.uuid4().hex,
            camera_id=settings.camera_id,
            zone=settings.zone,
            image_b64=base64.b64encode(jpeg).decode(),
        )
        payload = job.model_dump_json().encode()
        if js is not None:
            await js.publish(settings.jobs_subject, payload)
            transport = "jetstream"
        else:
            await nc.publish(settings.jobs_subject, payload)
            transport = "core"
        JOBS_PUBLISHED.labels(settings.camera_id, settings.zone, transport).inc()
        published += 1
        logger.info("Published job %s (%s/%s) [%s frames sent]", job.job_id, settings.camera_id, settings.zone, published)

        await _sleep_or_stop(stop, settings.sample_interval_seconds)

    logger.info("Shutting down")
    await nc.drain()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

"""Headless agent worker: jobs.images -> core.analyze_image -> observations.

Subscribes to the jobs subject in a queue group so N replicas load-balance.
Each job is decoded, run through the existing core pipeline (in a thread
executor — the Gemini call is blocking), and the result is published as a
structured Observation. Failures publish an error observation instead of
crashing the worker.
"""

import asyncio
import json
import logging
import signal

import nats

from agent.config import Settings, load_settings
from agent.health import start_health_server
from agent.messages import ImageJob, Observation
from core.vision import analyze_image

logger = logging.getLogger("agent.worker")


async def handle_job(nc, settings: Settings, msg) -> None:
    """Process one job message and publish an Observation (result or error)."""
    try:
        job = ImageJob.model_validate_json(msg.data)
    except Exception:
        logger.exception("Discarding malformed job message")
        obs = Observation(
            job_id="unknown",
            camera_id="unknown",
            worker_id=settings.worker_id,
            error="malformed job message",
        )
        await nc.publish(settings.obs_subject, obs.model_dump_json().encode())
        return

    try:
        analysis = await asyncio.to_thread(analyze_image, job.image_bytes(), job.zone)
        obs = Observation(
            job_id=job.job_id,
            camera_id=job.camera_id,
            zone=job.zone,
            worker_id=settings.worker_id,
            analysis=analysis,
        )
        logger.info(
            "Job %s (camera %s, zone %s) analyzed: %s objects",
            job.job_id,
            job.camera_id,
            job.zone,
            len(analysis.objects),
        )
    except Exception as exc:
        logger.exception("Job %s failed", job.job_id)
        obs = Observation(
            job_id=job.job_id,
            camera_id=job.camera_id,
            zone=job.zone,
            worker_id=settings.worker_id,
            error=f"{type(exc).__name__}: {exc}",
        )
    await nc.publish(settings.obs_subject, obs.model_dump_json().encode())


async def run() -> None:
    settings = load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    nc = await nats.connect(
        settings.nats_url,
        max_reconnect_attempts=-1,  # keep retrying; readiness probe reports the gap
        reconnect_time_wait=2,
    )
    logger.info("Connected to NATS at %s as %s", settings.nats_url, settings.worker_id)

    health = start_health_server(settings.health_port, ready_check=lambda: nc.is_connected)
    logger.info("Health server on :%s (/healthz, /readyz)", settings.health_port)

    async def on_message(msg):
        await handle_job(nc, settings, msg)

    await nc.subscribe(settings.jobs_subject, queue=settings.queue_group, cb=on_message)
    logger.info("Subscribed to %s (queue group %s)", settings.jobs_subject, settings.queue_group)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows event loop: fall back to KeyboardInterrupt for SIGINT.
            signal.signal(sig, lambda *_: stop.set())

    await stop.wait()
    logger.info("Shutting down")
    health.shutdown()
    await nc.drain()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

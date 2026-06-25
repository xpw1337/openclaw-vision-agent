"""Headless agent worker: jobs.images -> core.analyze_image -> observations.

Subscribes to the jobs subject in a queue group so N replicas load-balance.
Each job is decoded, run through the existing core pipeline (in a thread
executor — the Gemini call is blocking), and the result is published as a
structured Observation. Failures publish an error observation instead of
crashing the worker.
"""

import asyncio
import logging
import signal
import time

import nats

from agent.config import Settings, load_settings
from agent.health import start_health_server
from agent.messages import DeadLetterJob, ImageJob, Observation
from agent.metrics import ANALYZE_DURATION, DLQ_MESSAGES, JOBS_PROCESSED, JOBS_RETRIED
from agent.retry import backoff_delay, classify_exception
from core.vision import analyze_image

logger = logging.getLogger("agent.worker")


async def _publish_observation(nc, settings: Settings, obs: Observation) -> None:
    await nc.publish(settings.obs_subject, obs.model_dump_json().encode())


async def _publish_dlq(
    nc,
    settings: Settings,
    *,
    job_id: str,
    camera_id: str,
    zone: str,
    attempts: int,
    reason: str,
    terminal: bool,
    job_published_at=None,
) -> None:
    failed = DeadLetterJob(
        job_id=job_id,
        camera_id=camera_id,
        zone=zone,
        worker_id=settings.worker_id,
        attempts=attempts,
        reason=reason,
        terminal=terminal,
        job_published_at=job_published_at,
    )
    await nc.publish(settings.dlq_subject, failed.model_dump_json().encode())
    DLQ_MESSAGES.labels(terminal=str(terminal).lower()).inc()


async def _analyze_with_retries(job: ImageJob, settings: Settings, sleep=asyncio.sleep) -> tuple[Observation, int, str | None, bool]:
    attempts = 0
    last_reason: str | None = None
    last_terminal = False
    started = time.perf_counter()

    try:
        while attempts <= settings.max_retries:
            attempts += 1
            try:
                analysis = await asyncio.to_thread(analyze_image, job.image_bytes(), job.zone)
                obs = Observation(
                    job_id=job.job_id,
                    camera_id=job.camera_id,
                    zone=job.zone,
                    worker_id=settings.worker_id,
                    job_published_at=job.timestamp,
                    analysis=analysis,
                )
                logger.info(
                    "Job %s (camera %s, zone %s) analyzed: %s objects",
                    job.job_id,
                    job.camera_id,
                    job.zone,
                    len(analysis.objects),
                )
                JOBS_PROCESSED.labels(result="success").inc()
                return obs, attempts, None, False
            except Exception as exc:
                decision = classify_exception(exc)
                last_reason = decision.reason
                last_terminal = decision.terminal
                if decision.retryable and attempts <= settings.max_retries:
                    delay = backoff_delay(
                        attempts,
                        base=settings.retry_base_delay_seconds,
                        maximum=settings.retry_max_delay_seconds,
                    )
                    JOBS_RETRIED.inc()
                    logger.warning(
                        "Job %s failed attempt %s/%s, retrying in %.1fs: %s",
                        job.job_id,
                        attempts,
                        settings.max_retries + 1,
                        delay,
                        decision.reason,
                    )
                    await sleep(delay)
                    continue
                logger.exception("Job %s failed", job.job_id)
                break
    finally:
        ANALYZE_DURATION.observe(time.perf_counter() - started)

    obs = Observation(
        job_id=job.job_id,
        camera_id=job.camera_id,
        zone=job.zone,
        worker_id=settings.worker_id,
        job_published_at=job.timestamp,
        error=last_reason or "unknown analysis failure",
    )
    JOBS_PROCESSED.labels(result="error").inc()
    return obs, attempts, last_reason, last_terminal


async def handle_job(nc, settings: Settings, msg, *, sleep=asyncio.sleep) -> None:
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
        await _publish_observation(nc, settings, obs)
        await _publish_dlq(
            nc,
            settings,
            job_id="unknown",
            camera_id="unknown",
            zone="unknown",
            attempts=0,
            reason="malformed job message",
            terminal=True,
        )
        JOBS_PROCESSED.labels(result="malformed").inc()
        return

    obs, attempts, failure_reason, terminal = await _analyze_with_retries(job, settings, sleep=sleep)
    await _publish_observation(nc, settings, obs)
    if failure_reason is not None:
        await _publish_dlq(
            nc,
            settings,
            job_id=job.job_id,
            camera_id=job.camera_id,
            zone=job.zone,
            attempts=attempts,
            reason=failure_reason,
            terminal=terminal,
            job_published_at=job.timestamp,
        )


async def handle_jetstream_job(nc, settings: Settings, msg, *, sleep=asyncio.sleep) -> None:
    """Process a JetStream message and ack/nak around durable delivery."""
    try:
        await handle_job(nc, settings, msg, sleep=sleep)
    except Exception:
        logger.exception("JetStream job handling failed before completion; requesting redelivery")
        try:
            await msg.nak()
        except TypeError:
            await msg.nak(delay=1)
        return
    await msg.ack()


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

    if settings.jetstream_enabled:
        js = nc.jetstream()

        async def on_message(msg):
            await handle_jetstream_job(nc, settings, msg)

        await js.subscribe(
            settings.jobs_subject,
            queue=settings.queue_group,
            durable=settings.jobs_consumer,
            manual_ack=True,
            cb=on_message,
        )
        logger.info(
            "Subscribed to JetStream %s (consumer %s, queue group %s)",
            settings.jobs_subject,
            settings.jobs_consumer,
            settings.queue_group,
        )
    else:
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

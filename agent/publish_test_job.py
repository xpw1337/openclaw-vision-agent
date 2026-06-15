"""Dev/acceptance script: publish one image job and print the observation.

Usage:
    python -m agent.publish_test_job path/to/image.jpg [--camera-id cam-1]

Publishes an ImageJob to the jobs subject, subscribes to the observations
subject, and prints the first observation matching the job_id. Honors the same
NATS_URL / JOBS_SUBJECT / OBS_SUBJECT env vars as the worker.
"""

import argparse
import asyncio
import base64
import json
import sys
import uuid

import nats

from agent.config import load_settings
from agent.messages import ImageJob


async def run(image_path: str, camera_id: str, timeout: float) -> int:
    settings = load_settings()
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    job = ImageJob(job_id=str(uuid.uuid4()), camera_id=camera_id, image_b64=image_b64)

    nc = await nats.connect(settings.nats_url)
    sub = await nc.subscribe(settings.obs_subject)
    await nc.publish(settings.jobs_subject, job.model_dump_json().encode())
    print(f"Published job {job.job_id} to {settings.jobs_subject}; waiting on {settings.obs_subject}...")

    try:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                print("Timed out waiting for an observation", file=sys.stderr)
                return 1
            msg = await sub.next_msg(timeout=remaining)
            obs = json.loads(msg.data)
            if obs.get("job_id") == job.job_id:
                print(json.dumps(obs, indent=2))
                return 0 if obs.get("error") is None else 2
    finally:
        await nc.drain()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Path to an image file")
    parser.add_argument("--camera-id", default="cam-test")
    parser.add_argument("--timeout", type=float, default=120.0, help="Seconds to wait for the observation")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.image, args.camera_id, args.timeout)))


if __name__ == "__main__":
    main()

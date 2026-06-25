"""FastAPI read API for the fused area summary.

Routes live on a router that depends on `get_store`, so tests can mount the
router with a fake store and skip the connecting lifespan. The module-level
`app` wires the real Postgres/Redis/NATS connections for uvicorn.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import nats
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from fusion.config import load_settings
from fusion.consumer import Consumer
from fusion.db import Database
from fusion.store import Store

logger = logging.getLogger("fusion.api")
_DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "dashboard"

router = APIRouter()


def get_store(request: Request) -> Store:
    return request.app.state.store


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(_DASHBOARD_DIR / "index.html")


@router.get("/zones")
async def zones(store: Store = Depends(get_store)) -> dict:
    return {"zones": await store.list_zones()}


@router.get("/area")
async def area(store: Store = Depends(get_store)) -> dict:
    return await store.get_area()


@router.get("/zone/{zone_id}")
async def zone(zone_id: str, store: Store = Depends(get_store)) -> dict:
    if zone_id not in await store.list_zones():
        raise HTTPException(status_code=404, detail=f"unknown zone: {zone_id}")
    return await store.get_zone(zone_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()

    db = Database(settings.database_url, settings.db_password)
    store = Store(settings.redis_url)
    await db.connect()
    await store.connect()
    logger.info("Connected to Postgres and Redis")

    nc = await nats.connect(
        settings.nats_url, max_reconnect_attempts=-1, reconnect_time_wait=2
    )
    consumer = Consumer(nc, settings.obs_subject, db, store)
    await consumer.start()
    logger.info("Fusion consumer running on %s", settings.obs_subject)

    app.state.db = db
    app.state.store = store
    app.state.nc = nc
    app.state.consumer = consumer
    try:
        yield
    finally:
        await consumer.stop()
        await nc.drain()
        await store.close()
        await db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Surveillance Fusion API", lifespan=lifespan)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=_DASHBOARD_DIR), name="static")
    return app


app = create_app()

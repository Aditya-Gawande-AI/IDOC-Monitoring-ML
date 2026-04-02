from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging
from app.jobs.scheduler import SchedulerService

configure_logging()
scheduler_service = SchedulerService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await scheduler_service.start()
    try:
        yield
    finally:
        await scheduler_service.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router)

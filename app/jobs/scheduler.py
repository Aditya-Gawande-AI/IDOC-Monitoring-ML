from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.ml.training import TrainingService
from app.services.ingestion import IngestionService

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._ingestion = IngestionService()
        self._training = TrainingService()
        self.last_ingestion: dict | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def run_ingestion_once(self) -> dict:
        result = await self._ingestion.pull_and_store()
        self.last_ingestion = result
        await self._ensure_monthly_training()
        return result

    def run_training_once(self) -> dict:
        return self._training.train_monthly()

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.run_ingestion_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scheduled ingestion failed: %s", exc)
            await asyncio.sleep(max(60, settings.fetch_interval_minutes * 60))

    async def _ensure_monthly_training(self) -> None:
        current_month = datetime.now(timezone.utc).strftime("%Y%m")
        latest_month = self._training.latest_training_month()
        if latest_month == current_month:
            return

        result = self._training.train_monthly()
        logger.info("Monthly training check result: %s", result)

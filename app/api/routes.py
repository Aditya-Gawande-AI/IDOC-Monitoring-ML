from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.data.storage import load_training_registry
from app.jobs.scheduler import SchedulerService
from app.ml.inference import InferenceService

router = APIRouter()
_inference = InferenceService()


def get_scheduler() -> SchedulerService:
    from app.main import scheduler_service

    return scheduler_service


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/jobs/ingest")
async def ingest_once(scheduler: SchedulerService = Depends(get_scheduler)) -> dict:
    return await scheduler.run_ingestion_once()


@router.get("/jobs/train")
def train_once(scheduler: SchedulerService = Depends(get_scheduler)) -> dict:
    return scheduler.run_training_once()


@router.get("/jobs/training-registry")
def training_registry() -> dict:
    return load_training_registry()


@router.get("/insights/anomaly-detection")
def anomaly_detection() -> dict:
    return _inference.anomaly_detection()


@router.get("/insights/root-cause-clustering")
def root_cause_clustering() -> dict:
    return _inference.root_cause_clustering()


@router.get("/insights/volume-forecast")
def volume_forecast(
    period: Literal["hour", "day", "week", "month"] = Query(default="hour"),
    target_datetime: str | None = Query(default=None),
) -> dict:
    return _inference.volume_forecast(period=period, target_datetime=target_datetime)


@router.get("/insights/partner-health")
def partner_health() -> dict:
    return _inference.partner_health()


@router.get("/insights/dynamic-error-clustering")
def dynamic_error_clustering() -> dict:
    return _inference.dynamic_error_clustering()


@router.get("/insights/adaptive-thresholding")
def adaptive_thresholding() -> dict:
    return _inference.adaptive_thresholding()


@router.get("/insights/partner-behavior")
def partner_behavior() -> dict:
    return _inference.partner_behavior()


@router.get("/insights/capacity-planning")
def capacity_planning() -> dict:
    return _inference.capacity_planning()

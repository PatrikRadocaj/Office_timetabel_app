"""Demand forecast routes including CSV upload."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import require_admin
from app.models.demand import (
    DailyDemandForecastCreate,
    DailyDemandForecastWriteResponse,
    DemandForecastBulkCreate,
    DemandForecastCreate,
    DemandForecastDayViewRead,
    DemandForecastRead,
)
from app.services.catalog_service import DemandService

router = APIRouter(prefix="/demand-forecasts", tags=["demand_forecasts"])
service = DemandService()


@router.get("", response_model=list[DemandForecastRead])
def list_demand(
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    _: dict = Depends(require_admin),
) -> list[dict]:
    return service.list(start_at=start_at, end_at=end_at)


@router.post("", response_model=DemandForecastRead)
def create_demand(payload: DemandForecastCreate, _: dict = Depends(require_admin)) -> dict:
    return service.create(payload)


@router.post("/daily", response_model=DailyDemandForecastWriteResponse)
def create_daily_demand(payload: DailyDemandForecastCreate, _: dict = Depends(require_admin)) -> dict:
    return service.create_daily(payload)


@router.post("/bulk")
def create_bulk_demand(payload: DemandForecastBulkCreate, _: dict = Depends(require_admin)) -> dict:
    return service.create_bulk(payload)


@router.get("/day-view", response_model=DemandForecastDayViewRead)
def get_day_view(
    office_id: str,
    forecast_date: date,
    interval_minutes: int = 30,
    _: dict = Depends(require_admin),
) -> dict:
    return service.day_view(office_id=office_id, forecast_date=forecast_date, interval_minutes=interval_minutes)


@router.post("/upload-csv")
async def upload_demand_csv(
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
) -> dict:
    return await service.ingest_csv(file)

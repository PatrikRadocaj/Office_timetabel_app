"""Demand forecast schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class DemandForecastCreate(BaseModel):
    office_id: str
    skill_id: str
    slot_start: datetime
    slot_end: datetime
    required_agents: int = Field(ge=1, le=10000)
    priority: int = Field(default=3, ge=1, le=5)


class DemandForecastRead(DemandForecastCreate):
    id: str
    created_at: datetime | str
    updated_at: datetime | str


class DemandForecastBulkCreate(BaseModel):
    items: list[DemandForecastCreate] = Field(default_factory=list)


class SkillDemandSeriesCreate(BaseModel):
    skill_id: str
    priority: int = Field(default=3, ge=1, le=5)
    quantities: list[int] = Field(default_factory=list)

    @field_validator("quantities")
    @classmethod
    def validate_quantities(cls, value: list[int]) -> list[int]:
        for qty in value:
            if qty < 0:
                raise ValueError("Demand quantity cannot be negative")
            if qty > 10000:
                raise ValueError("Demand quantity cannot exceed 10000")
        return value


class DailyDemandForecastCreate(BaseModel):
    office_id: str
    date: date
    interval_minutes: int = Field(default=30, ge=30, le=60)
    skill_demands: list[SkillDemandSeriesCreate] = Field(default_factory=list, min_length=1)
    replace_existing_day: bool = True

    @field_validator("interval_minutes")
    @classmethod
    def validate_interval_minutes(cls, value: int) -> int:
        if value not in {30, 60}:
            raise ValueError("interval_minutes must be 30 or 60")
        return value

    @field_validator("skill_demands")
    @classmethod
    def validate_unique_skill_ids(cls, value: list[SkillDemandSeriesCreate]) -> list[SkillDemandSeriesCreate]:
        skill_ids = [entry.skill_id for entry in value]
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("Each skill can appear only once in skill_demands")
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> "DailyDemandForecastCreate":
        expected_slots = (24 * 60) // self.interval_minutes
        non_zero_values = 0

        for entry in self.skill_demands:
            if len(entry.quantities) != expected_slots:
                raise ValueError(
                    f"Skill {entry.skill_id} must include exactly {expected_slots} quantities for "
                    f"{self.interval_minutes}-minute intervals"
                )
            non_zero_values += sum(1 for qty in entry.quantities if qty > 0)

        if non_zero_values == 0:
            raise ValueError("At least one interval must have demand greater than 0")

        return self


class DailyDemandForecastWriteResponse(BaseModel):
    message: str
    office_id: str
    date: date
    interval_minutes: int
    created_count: int
    deleted_count: int
    forecast_batch_id: str
    document_count: int = 1
    represented_slot_count: int = 0


class DayDemandBlockRead(BaseModel):
    block_start: str
    slot_start: datetime | str
    slot_end: datetime | str
    totals_by_skill: dict[str, int] = Field(default_factory=dict)
    total_required: int = 0
    coverage_by_skill: dict[str, int] = Field(default_factory=dict)
    total_covered: int = 0
    coverage_gap: int = 0
    coverage_ratio: float = 1.0


class DemandForecastDayViewRead(BaseModel):
    office_id: str
    date: date
    interval_minutes: int
    skill_ids: list[str]
    blocks: list[DayDemandBlockRead] = Field(default_factory=list)
    coverage_schedule_id: str | None = None
    coverage_generated_at: datetime | str | None = None

"""Pydantic v2 schemas for the HR / Workforce domain."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DepartmentBreakdown(BaseModel):
    """Headcount and leave figures for a single department within a tenant."""

    model_config = ConfigDict(frozen=True)

    department_name: str
    headcount: int = Field(ge=0)
    open_positions: int = Field(ge=0)
    pending_leave_requests: int = Field(ge=0)


class WorkforceSummaryResponse(BaseModel):
    """Response body for `GET /api/v1/hr/summary`."""

    model_config = ConfigDict(frozen=True)

    tenant_id: str
    generated_at: datetime
    total_employees: int = Field(ge=0)
    active_contracts: int = Field(ge=0)
    pending_leave_requests: int = Field(ge=0)
    departments: list[DepartmentBreakdown]

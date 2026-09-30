"""Pydantic v2 schemas for the HR / Workforce domain."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

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


# --- Real, DB-backed employee writes ----------------------------------------
#
# Distinct from DepartmentBreakdown/WorkforceSummaryResponse above (that's
# simulated aggregate data for the summary endpoint). These back the real
# POST/PUT/DELETE /api/v1/hr/employees endpoints and the `employees` table
# in app/db/models.py.


class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class EmployeeCreate(BaseModel):
    """Body for `POST /api/v1/hr/employees`."""

    full_name: str = Field(min_length=1, max_length=200)
    department: str = Field(min_length=1, max_length=120)
    job_title: str = Field(min_length=1, max_length=120)
    monthly_salary: float = Field(gt=0)
    status: EmployeeStatus = EmployeeStatus.ACTIVE


class EmployeeUpdate(BaseModel):
    """
    Body for `PUT /api/v1/hr/employees/{employee_id}`. Every field is
    optional — only the fields actually sent are changed, everything else
    on the stored record is left untouched.
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    department: str | None = Field(default=None, min_length=1, max_length=120)
    job_title: str | None = Field(default=None, min_length=1, max_length=120)
    monthly_salary: float | None = Field(default=None, gt=0)
    status: EmployeeStatus | None = None


class EmployeeOut(BaseModel):
    """A real, persisted employee record."""

    model_config = ConfigDict(frozen=True)

    id: str
    tenant_id: str
    full_name: str
    department: str
    job_title: str
    monthly_salary: float
    status: EmployeeStatus
    created_at: datetime
    updated_at: datetime


class AuditWriteStatus(str, Enum):
    """
    Whether the real audit event this write is supposed to emit to
    nexus-audit-service actually landed. Mirrors the project's own
    Operational/Attention Required honesty rule, scoped to this one
    concern: the domain write below always reflects what's really in
    this service's own DB, but `audit` never claims "recorded" unless
    nexus-audit-service genuinely accepted the event — see
    app/services/hr/audit_client.py.
    """

    RECORDED = "recorded"
    UNAVAILABLE = "unavailable"


class EmployeeWriteResult(BaseModel):
    """Response body for `POST` and `PUT` on `/api/v1/hr/employees`."""

    model_config = ConfigDict(frozen=True)

    employee: EmployeeOut
    audit: AuditWriteStatus
    audit_detail: str | None = None


class EmployeeDeleteResult(BaseModel):
    """Response body for `DELETE /api/v1/hr/employees/{employee_id}`."""

    model_config = ConfigDict(frozen=True)

    deleted_id: str
    audit: AuditWriteStatus
    audit_detail: str | None = None

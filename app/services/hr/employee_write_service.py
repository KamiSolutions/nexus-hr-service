"""
Real, DB-backed write path for the HR / Workforce domain.

Distinct from workforce_service.py's `get_workforce_summary`, which
aggregates simulated department figures for the read-only summary
endpoint — this module owns Nexus's own real `employees` table: slice 2
of the platform's domain writes (financials was slice 1). Every write
here also emits a real audit event to nexus-audit-service via
`audit_client.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.db.models import EmployeeModel
from app.schemas.hr import (
    EmployeeCreate,
    EmployeeDeleteResult,
    EmployeeOut,
    EmployeeUpdate,
    EmployeeWriteResult,
)
from app.services.hr.audit_client import record_audit_event

_UPDATABLE_FIELDS: tuple[str, ...] = (
    "full_name",
    "department",
    "job_title",
    "monthly_salary",
    "status",
)


def _to_out(row: EmployeeModel) -> EmployeeOut:
    return EmployeeOut(
        id=row.id,
        tenant_id=row.tenant_id,
        full_name=row.full_name,
        department=row.department,
        job_title=row.job_title,
        monthly_salary=row.monthly_salary,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_employees(*, tenant_id: str) -> list[EmployeeOut]:
    """Read-only listing of this tenant's real, written employee records, newest first."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(EmployeeModel)
            .where(EmployeeModel.tenant_id == tenant_id)
            .order_by(EmployeeModel.created_at.desc())
        )
        return [_to_out(row) for row in result.scalars().all()]


async def create_employee(payload: EmployeeCreate, *, tenant_id: str, token: str) -> EmployeeWriteResult:
    now = datetime.now(timezone.utc)
    row = EmployeeModel(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        full_name=payload.full_name,
        department=payload.department,
        job_title=payload.job_title,
        monthly_salary=payload.monthly_salary,
        status=payload.status.value,
        created_at=now,
        updated_at=now,
    )
    async with AsyncSessionLocal() as session:
        session.add(row)
        await session.commit()

    async with httpx.AsyncClient(timeout=settings.AUDIT_SERVICE_TIMEOUT_SECONDS) as client:
        audit_status, audit_detail = await record_audit_event(
            client,
            token=token,
            tenant_id=tenant_id,
            action="employee.created",
            resource_type="employee",
            resource_id=row.id,
            metadata={"full_name": row.full_name, "department": row.department},
        )

    return EmployeeWriteResult(employee=_to_out(row), audit=audit_status, audit_detail=audit_detail)


async def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    *,
    tenant_id: str,
    token: str,
) -> EmployeeWriteResult:
    async with AsyncSessionLocal() as session:
        row = await session.get(EmployeeModel, employee_id)
        if row is None or row.tenant_id != tenant_id:
            # Tenant-scoped, fail closed — a real employee that belongs to a
            # different tenant is reported identically to one that doesn't
            # exist at all, never leaked as a 403 that would confirm it exists.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")

        changed_fields: dict[str, str] = {}
        for field in _UPDATABLE_FIELDS:
            new_value = getattr(payload, field)
            if new_value is None:
                continue
            new_value = new_value.value if hasattr(new_value, "value") else new_value
            if getattr(row, field) != new_value:
                changed_fields[field] = str(new_value)
            setattr(row, field, new_value)

        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        out = _to_out(row)

    async with httpx.AsyncClient(timeout=settings.AUDIT_SERVICE_TIMEOUT_SECONDS) as client:
        audit_status, audit_detail = await record_audit_event(
            client,
            token=token,
            tenant_id=tenant_id,
            action="employee.updated",
            resource_type="employee",
            resource_id=employee_id,
            metadata=changed_fields or {"note": "request contained no changed fields"},
        )

    return EmployeeWriteResult(employee=out, audit=audit_status, audit_detail=audit_detail)


async def delete_employee(employee_id: str, *, tenant_id: str, token: str) -> EmployeeDeleteResult:
    async with AsyncSessionLocal() as session:
        row = await session.get(EmployeeModel, employee_id)
        if row is None or row.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
        await session.delete(row)
        await session.commit()

    async with httpx.AsyncClient(timeout=settings.AUDIT_SERVICE_TIMEOUT_SECONDS) as client:
        audit_status, audit_detail = await record_audit_event(
            client,
            token=token,
            tenant_id=tenant_id,
            action="employee.deleted",
            resource_type="employee",
            resource_id=employee_id,
        )

    return EmployeeDeleteResult(deleted_id=employee_id, audit=audit_status, audit_detail=audit_detail)

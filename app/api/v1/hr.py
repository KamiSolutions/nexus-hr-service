"""
HR / Workforce router.

Every route here requires both:
  * a resolved tenant context (`get_tenant_context`) — data isolation, and
  * the `hr:view` (or stricter) security scope — RBAC.

`hr` matches the module name in the combined role model
(lib/permissions.ts / app/core/rbac.py).

As of this round, this router owns nexus-hr-service's first real domain
writes: `POST`/`PUT`/`DELETE` on `/employees`, each backed by a real DB
table (`app/db/models.py`'s `EmployeeModel`) and each emitting a real
audit event to nexus-audit-service (`app/services/hr/audit_client.py`).
`DELETE` is deliberately gated behind `hr:manage` rather than `hr:create`
— HR_MANAGER (and EMPLOYEE, per self-service leave-style flows) can
create/edit employee records but not delete them; only SUPER_ADMIN/
GROUP_ADMIN-level `manage` roles can. Note COMPANY_ADMIN holds `hr:view`
and `hr:approve` but *not* `hr:create` — a deliberate asymmetry already
present in the RBAC table, not something to "fix" here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Security, status

from app.dependencies.auth import get_current_user, oauth2_scheme
from app.dependencies.tenant import get_tenant_context
from app.schemas.auth import CurrentUser
from app.schemas.hr import (
    EmployeeCreate,
    EmployeeDeleteResult,
    EmployeeOut,
    EmployeeUpdate,
    EmployeeWriteResult,
    WorkforceSummaryResponse,
)
from app.schemas.tenant import TenantContext
from app.services.hr.employee_write_service import (
    create_employee,
    delete_employee,
    list_employees,
    update_employee,
)
from app.services.hr.workforce_service import get_workforce_summary

router = APIRouter(prefix="/hr", tags=["hr"])


@router.get(
    "/summary",
    response_model=WorkforceSummaryResponse,
    summary="Tenant-wide workforce summary",
)
async def read_workforce_summary(
    tenant: TenantContext = Depends(get_tenant_context),
    current_user: CurrentUser = Security(get_current_user, scopes=["hr:view"]),
) -> WorkforceSummaryResponse:
    """
    Aggregate headcount, active-contract and pending-leave figures across
    every department for this tenant.

    Restricted to principals holding `hr:view` — e.g. HR_MANAGER,
    COMPANY_ADMIN, GROUP_ADMIN, TEAM_LEAD, EMPLOYEE, or AUDITOR — never
    DRIVER or FLEET_MANAGER, whose scopes don't include any `hr:*`
    permission.
    """
    # current_user is available for audit logging / row-level narrowing;
    # referenced here to make that intent explicit even though this demo
    # endpoint doesn't yet write an audit trail.
    del current_user
    return await get_workforce_summary(tenant)


@router.get(
    "/employees",
    response_model=list[EmployeeOut],
    summary="List this tenant's real, written employee records",
)
async def read_employees(
    tenant: TenantContext = Depends(get_tenant_context),
    current_user: CurrentUser = Security(get_current_user, scopes=["hr:view"]),
) -> list[EmployeeOut]:
    del current_user
    return await list_employees(tenant_id=tenant.tenant_id)


@router.post(
    "/employees",
    response_model=EmployeeWriteResult,
    status_code=status.HTTP_201_CREATED,
    summary="Create a real employee record and emit a real audit event",
)
async def write_new_employee(
    payload: EmployeeCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    current_user: CurrentUser = Security(get_current_user, scopes=["hr:create"]),
    token: str = Depends(oauth2_scheme),
) -> EmployeeWriteResult:
    del current_user
    return await create_employee(payload, tenant_id=tenant.tenant_id, token=token)


@router.put(
    "/employees/{employee_id}",
    response_model=EmployeeWriteResult,
    summary="Update a real employee record and emit a real audit event",
)
async def write_employee_update(
    employee_id: str,
    payload: EmployeeUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    current_user: CurrentUser = Security(get_current_user, scopes=["hr:create"]),
    token: str = Depends(oauth2_scheme),
) -> EmployeeWriteResult:
    del current_user
    return await update_employee(employee_id, payload, tenant_id=tenant.tenant_id, token=token)


@router.delete(
    "/employees/{employee_id}",
    response_model=EmployeeDeleteResult,
    summary="Delete a real employee record and emit a real audit event (hr:manage only)",
)
async def write_employee_delete(
    employee_id: str,
    tenant: TenantContext = Depends(get_tenant_context),
    current_user: CurrentUser = Security(get_current_user, scopes=["hr:manage"]),
    token: str = Depends(oauth2_scheme),
) -> EmployeeDeleteResult:
    del current_user
    return await delete_employee(employee_id, tenant_id=tenant.tenant_id, token=token)

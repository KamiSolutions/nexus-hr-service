"""
HR / Workforce router.

Every route here requires both:
  * a resolved tenant context (`get_tenant_context`) — data isolation, and
  * the `hr:view` (or stricter) security scope — RBAC.

`hr` matches the module name in the combined role model
(lib/permissions.ts / app/core/rbac.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Security

from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_tenant_context
from app.schemas.auth import CurrentUser
from app.schemas.hr import WorkforceSummaryResponse
from app.schemas.tenant import TenantContext
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

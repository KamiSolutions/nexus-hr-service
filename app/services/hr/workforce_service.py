"""
HR / Workforce domain service.

Houses the async data-fetching logic used by the HR router. Kept separate
from the route module so it can be reused by, e.g., a background worker
or a webhook handler without importing FastAPI. Mirrors the same
concurrent-fan-out pattern nexus-financials-service uses for its policy
providers — here fanning out across departments instead of third-party
providers, since HR data in this domain is internal (payroll/timesheet
integrations like Sage/PaySpace are P1, not connected yet).
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone

from app.schemas.hr import DepartmentBreakdown, WorkforceSummaryResponse
from app.schemas.tenant import TenantContext

# Departments a funeral-parlour-network tenant might track headcount for.
_KNOWN_DEPARTMENTS: tuple[str, ...] = (
    "Mortuary Operations",
    "Client Services",
    "Finance & Admin",
    "Fleet & Logistics",
    "Management",
)


async def _fetch_department_snapshot(tenant: TenantContext, department_name: str) -> DepartmentBreakdown:
    """
    Simulates one concurrent, non-blocking call out to an HR/payroll data
    source (e.g. Sage/PaySpace, once that integration exists) for this
    tenant's department headcount.

    Replace the body with a real `httpx.AsyncClient` call or DB query; the
    `asyncio.sleep` stands in for network/DB latency so
    `get_workforce_summary` genuinely demonstrates concurrent I/O rather
    than sequential mocking.
    """
    await asyncio.sleep(random.uniform(0.05, 0.2))

    rng = random.Random(f"{tenant.tenant_id}:{department_name}")
    return DepartmentBreakdown(
        department_name=department_name,
        headcount=rng.randint(3, 120),
        open_positions=rng.randint(0, 6),
        pending_leave_requests=rng.randint(0, 10),
    )


async def get_workforce_summary(tenant: TenantContext) -> WorkforceSummaryResponse:
    """
    Build the tenant's workforce summary by fanning out to every known
    department concurrently via `asyncio.gather`, then aggregating the
    results.
    """
    department_snapshots = await asyncio.gather(
        *(_fetch_department_snapshot(tenant, department) for department in _KNOWN_DEPARTMENTS)
    )

    total_employees = sum(d.headcount for d in department_snapshots)
    pending_leave_requests = sum(d.pending_leave_requests for d in department_snapshots)

    # Active contracts would normally come from a separate contracts-ledger
    # query, run concurrently alongside the department fan-out above.
    active_contracts = round(total_employees * 0.94)

    return WorkforceSummaryResponse(
        tenant_id=tenant.tenant_id,
        generated_at=datetime.now(timezone.utc),
        total_employees=total_employees,
        active_contracts=active_contracts,
        pending_leave_requests=pending_leave_requests,
        departments=list(department_snapshots),
    )

"""
RBAC + persistence + honest audit-degradation tests for the real
POST/PUT/DELETE `/employees` endpoints — slice 2's HR write path,
following the same pattern proved in nexus-financials-service's
`test_policy_writes.py`.

The audit call each write makes genuinely fails here (nexus-audit-service
isn't running during `pytest`), and that's deliberate: it proves the
honest-degradation path for real rather than mocking it — the domain
write still succeeds (it really did land in this service's own DB), but
`audit` in the response comes back "unavailable", never a fabricated
"recorded". The positive "audit really recorded" path is proven
separately against a real running nexus-audit-service in the combined
live HTTP smoke test (see the plan doc), matching this project's
established bar for what counts as verified.
"""

from __future__ import annotations

import datetime as dt

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

ROLE_SCOPES = {
    "HR_MANAGER": ["dashboard:view", "hr:view", "hr:create", "hr:approve", "reports:view"],
    "COMPANY_ADMIN": ["dashboard:view", "hr:view", "hr:approve"],
    "SUPER_ADMIN": ["hr:view", "hr:create", "hr:approve", "hr:manage"],
    "DRIVER": ["dashboard:view", "vehicles:view"],
}


def _mint(role: str, tenant_id: str = "demo_sandbox") -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": "test-user",
        "scopes": ROLE_SCOPES[role],
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=5)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _auth(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_mint(role)}"}


def _create_payload(**overrides):
    payload = {
        "full_name": "Jane Test",
        "department": "Operations",
        "job_title": "Coordinator",
        "monthly_salary": 15000.0,
    }
    payload.update(overrides)
    return payload


def test_hr_manager_can_create_employee(client):
    r = client.post("/api/v1/hr/employees", json=_create_payload(), headers=_auth("HR_MANAGER"))
    assert r.status_code == 201
    body = r.json()
    assert body["employee"]["full_name"] == "Jane Test"
    assert body["employee"]["status"] == "active"
    assert body["employee"]["tenant_id"] == "demo_sandbox"
    # nexus-audit-service isn't running during pytest — this must stay
    # honest, never a fabricated "recorded".
    assert body["audit"] == "unavailable"
    assert body["audit_detail"]


def test_company_admin_forbidden_from_creating_employee(client):
    # COMPANY_ADMIN holds hr:view + hr:approve but not hr:create — a
    # deliberate asymmetry already present in the RBAC table.
    r = client.post("/api/v1/hr/employees", json=_create_payload(), headers=_auth("COMPANY_ADMIN"))
    assert r.status_code == 403


def test_driver_forbidden_from_creating_employee(client):
    r = client.post("/api/v1/hr/employees", json=_create_payload(), headers=_auth("DRIVER"))
    assert r.status_code == 403


def test_created_employee_is_listed_and_persisted(client):
    create = client.post(
        "/api/v1/hr/employees",
        json=_create_payload(full_name="List Test"),
        headers=_auth("HR_MANAGER"),
    )
    employee_id = create.json()["employee"]["id"]

    listing = client.get("/api/v1/hr/employees", headers=_auth("HR_MANAGER"))
    assert listing.status_code == 200
    assert any(e["id"] == employee_id for e in listing.json())


def test_hr_manager_can_update_employee(client):
    create = client.post(
        "/api/v1/hr/employees",
        json=_create_payload(full_name="Update Test"),
        headers=_auth("HR_MANAGER"),
    )
    employee_id = create.json()["employee"]["id"]

    r = client.put(
        f"/api/v1/hr/employees/{employee_id}",
        json={"status": "on_leave"},
        headers=_auth("HR_MANAGER"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["employee"]["status"] == "on_leave"
    # Untouched fields stay as they were.
    assert body["employee"]["full_name"] == "Update Test"


def test_update_unknown_employee_is_404(client):
    r = client.put(
        "/api/v1/hr/employees/does-not-exist",
        json={"status": "on_leave"},
        headers=_auth("HR_MANAGER"),
    )
    assert r.status_code == 404


def test_delete_requires_hr_manage_not_just_hr_create(client):
    create = client.post(
        "/api/v1/hr/employees",
        json=_create_payload(full_name="Delete Test"),
        headers=_auth("HR_MANAGER"),
    )
    employee_id = create.json()["employee"]["id"]

    # HR_MANAGER holds hr:create but not hr:manage — deletion is
    # deliberately restricted further than create/update.
    r = client.delete(f"/api/v1/hr/employees/{employee_id}", headers=_auth("HR_MANAGER"))
    assert r.status_code == 403


def test_super_admin_can_delete_employee(client):
    create = client.post(
        "/api/v1/hr/employees",
        json=_create_payload(full_name="Delete Test 2"),
        headers=_auth("SUPER_ADMIN"),
    )
    employee_id = create.json()["employee"]["id"]

    r = client.delete(f"/api/v1/hr/employees/{employee_id}", headers=_auth("SUPER_ADMIN"))
    assert r.status_code == 200
    assert r.json()["deleted_id"] == employee_id

    listing = client.get("/api/v1/hr/employees", headers=_auth("SUPER_ADMIN"))
    assert all(e["id"] != employee_id for e in listing.json())


def test_delete_unknown_employee_is_404(client):
    r = client.delete("/api/v1/hr/employees/does-not-exist", headers=_auth("SUPER_ADMIN"))
    assert r.status_code == 404


def test_no_token_unauthorized_on_write(client):
    assert client.post("/api/v1/hr/employees", json=_create_payload()).status_code == 401


def test_unknown_tenant_not_found_on_write(client):
    r = client.post(
        "/api/v1/hr/employees",
        json=_create_payload(),
        headers={**_auth("HR_MANAGER"), "X-Tenant-ID": "does_not_exist"},
    )
    assert r.status_code == 404

"""SQLAlchemy ORM models backing the real HR/Workforce writes."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmployeeModel(Base):
    """
    A real, tenant-scoped employee record — created/updated/deleted via
    `POST/PUT/DELETE /api/v1/hr/employees`. Distinct from the fan-out demo
    data `workforce_service.get_workforce_summary` still generates for
    `/hr/summary` (that endpoint aggregates simulated department figures;
    this table is Nexus's own real record of employees the tenant has
    actually entered here).
    """

    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    job_title: Mapped[str] = mapped_column(String(120), nullable=False)
    monthly_salary: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # "active" | "on_leave" | "terminated"
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

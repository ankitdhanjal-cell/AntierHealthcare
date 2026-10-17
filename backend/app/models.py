import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc)


def uid():
    return uuid.uuid4().hex


class Scoped:
    """Tenant + site ids on every record."""
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, default="t1")
    site_id: Mapped[str] = mapped_column(String(32), index=True, default="s1")


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    branding: Mapped[dict] = mapped_column(JSON, default=dict)  # logo_url, primary_color, sender_name
    profile: Mapped[dict] = mapped_column(JSON, default=dict)


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(200))


class Setting(Base):
    """Configurable lists/records: themes, questions, sla, routing, kpis."""
    __tablename__ = "settings"
    tenant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class Department(Scoped, Base):
    __tablename__ = "departments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    sees_all: Mapped[bool] = mapped_column(Boolean, default=False)
    # {module: [view, create, approve, admin]}
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Scoped, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(200), default="")
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"))
    department_ids: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    invited: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(5), default="en")
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Muscat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    role: Mapped[Role] = relationship(lazy="joined")


class Patient(Scoped, Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    mrn: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(30), default="")
    language: Mapped[str] = mapped_column(String(5), default="en")
    department_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attending: Mapped[str] = mapped_column(String(200), default="")
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FeedbackRequest(Scoped, Base):
    __tablename__ = "feedback_requests"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    token: Mapped[str] = mapped_column(String(40), unique=True, index=True, default=lambda: uuid.uuid4().hex[:16])
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    department_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, sent, answered
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    google_invited: Mapped[bool] = mapped_column(Boolean, default=False)
    google_clicked: Mapped[bool] = mapped_column(Boolean, default=False)


class Message(Scoped, Base):
    """Simulated WhatsApp channel."""
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    patient_id: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(5), default="out")
    body: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(5), default="en")
    link: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FeedbackResponse(Scoped, Base):
    __tablename__ = "feedback_responses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    request_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    department_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    rating: Mapped[int] = mapped_column(Integer)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)  # question_key -> 1..5
    text: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(5), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    # AI analysis (suggestion) and what the user accepted/edited
    ai: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | needs_review
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted: Mapped[dict] = mapped_column(JSON, default=dict)  # user-confirmed values
    sentiment: Mapped[str] = mapped_column(String(10), default="neutral", index=True)
    themes: Mapped[list] = mapped_column(JSON, default=list)
    urgency: Mapped[str] = mapped_column(String(10), default="low")
    case_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    patient: Mapped[Patient] = relationship(lazy="joined")


class Case(Scoped, Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    feedback_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(32))
    department_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    urgency: Mapped[str] = mapped_column(String(10), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="New", index=True)
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str] = mapped_column(Text, default="")
    breach_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    incident_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class CaseEvent(Scoped, Base):
    __tablename__ = "case_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # created, assigned, status, note, escalated, closed
    text: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(200), default="System")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Notification(Scoped, Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # assignment, sla_breach, ...
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(200), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EmailLog(Scoped, Base):
    __tablename__ = "email_log"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    to: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent | logged | failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Scoped, Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    user_name: Mapped[str] = mapped_column(String(200), default="System")
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(40))
    record_type: Mapped[str] = mapped_column(String(40), default="")
    record_id: Mapped[str] = mapped_column(String(40), default="", index=True)
    summary: Mapped[str] = mapped_column(String(400), default="")
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
    theme: Mapped[str] = mapped_column(String(10), default="light")
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
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ward: Mapped[str] = mapped_column(String(60), default="")


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
    channel: Mapped[str] = mapped_column(String(12), default="whatsapp")  # whatsapp | sms | qr
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
    channel: Mapped[str] = mapped_column(String(12), default="whatsapp")  # whatsapp | sms
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
    nps: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-10 likelihood to recommend
    attending: Mapped[str] = mapped_column(String(200), default="")
    staff_mentions: Mapped[list] = mapped_column(JSON, default=list)  # staff named in the comment
    compliment_shared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
    closing_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseEvent(Scoped, Base):
    __tablename__ = "case_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # created, assigned, status, note, escalated, closed
    text: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(200), default="System")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CaseCall(Scoped, Base):
    """Patient call-back made for a case (service recovery)."""
    __tablename__ = "case_calls"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(String(32), index=True)
    outcome: Mapped[str] = mapped_column(String(30))  # reached, apologised, resolved, follow_up, no_answer
    note: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(200), default="System")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Incident(Scoped, Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30), index=True)
    harm: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), default="Reported", index=True)
    department_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    location: Mapped[str] = mapped_column(String(120), default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    immediate_action: Mapped[str] = mapped_column(Text, default="")
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    reported_by: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    investigator_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sentinel: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    patient_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contributing_factors: Mapped[dict] = mapped_column(JSON, default=dict)  # {people: [..], process: [..], ...}
    why_chain: Mapped[list] = mapped_column(JSON, default=list)  # 5 Whys, in order
    root_cause: Mapped[str] = mapped_column(Text, default="")
    ai: Mapped[dict] = mapped_column(JSON, default=dict)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    breach_notified: Mapped[bool] = mapped_column(Boolean, default=False)


class IncidentEvent(Scoped, Base):
    __tablename__ = "incident_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # reported, triaged, assigned, status, note, fact, escalated, capa, closed, linked
    text: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(200), default="System")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)  # when it happened (facts) or was recorded


class Capa(Scoped, Base):
    """Corrective or preventive action, with an effectiveness check."""
    __tablename__ = "capas"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(12), default="corrective")  # corrective | preventive
    action: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="Open", index=True)  # Open, In progress, Completed
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_result: Mapped[str] = mapped_column(String(20), default="")  # "", effective, not_effective
    check_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    overdue_notified: Mapped[bool] = mapped_column(Boolean, default=False)


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


# ---------------- accreditation
class StandardChapter(Scoped, Base):
    __tablename__ = "standard_chapters"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)


class StandardElement(Scoped, Base):
    """A measurable element of a standard."""
    __tablename__ = "standard_elements"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    chapter_id: Mapped[str] = mapped_column(String(32), index=True)
    standard_code: Mapped[str] = mapped_column(String(20))
    standard_title: Mapped[str] = mapped_column(String(300))
    code: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Not met", index=True)  # Met, Partially met, Not met, Not applicable
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)


class Evidence(Scoped, Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    element_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # file | capa | audit_run
    title: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(300), default="")
    path: Mapped[str] = mapped_column(String(500), default="")
    source_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    added_by: Mapped[str] = mapped_column(String(200), default="System")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TracerRun(Scoped, Base):
    """Mock survey (tracer) of one chapter."""
    __tablename__ = "tracer_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    chapter_id: Mapped[str] = mapped_column(String(32), index=True)
    started_by: Mapped[str] = mapped_column(String(200), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TracerResult(Scoped, Base):
    __tablename__ = "tracer_results"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    element_id: Mapped[str] = mapped_column(String(32))
    result: Mapped[str] = mapped_column(String(20))  # Met, Partially met, Not met, Not applicable
    note: Mapped[str] = mapped_column(Text, default="")
    action_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class QualityAction(Scoped, Base):
    """Follow-up action from an accreditation gap, a tracer finding or an audit result."""
    __tablename__ = "quality_actions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    text: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(12))  # gap | tracer | audit
    source_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    element_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    department_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="Open", index=True)  # Open, In progress, Completed
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(200), default="System")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    overdue_notified: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------- audits
class AuditTemplate(Scoped, Base):
    __tablename__ = "audit_templates"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    items: Mapped[list] = mapped_column(JSON, default=list)  # [{key, text}]
    target: Mapped[float] = mapped_column(Float, default=90)  # compliance %
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditRun(Scoped, Base):
    """One audit of one department or ward for one month."""
    __tablename__ = "audit_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    template_id: Mapped[str] = mapped_column(String(32), index=True)
    department_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(String(80), default="")  # ward or area audited
    period: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    auditor_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(12), default="Scheduled", index=True)  # Scheduled | Completed
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    yes_count: Mapped[int] = mapped_column(Integer, default=0)
    no_count: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # compliance %
    comment: Mapped[str] = mapped_column(Text, default="")


class AuditAnswer(Scoped, Base):
    __tablename__ = "audit_answers"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    item_key: Mapped[str] = mapped_column(String(40))
    result: Mapped[str] = mapped_column(String(4))  # yes | no | na
    comment: Mapped[str] = mapped_column(Text, default="")
    photo_path: Mapped[str] = mapped_column(String(500), default="")
    action_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


# ---------------- indicators
class Indicator(Scoped, Base):
    __tablename__ = "indicators"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    definition: Mapped[str] = mapped_column(Text)
    numerator: Mapped[str] = mapped_column(Text)
    denominator: Mapped[str] = mapped_column(Text)
    multiplier: Mapped[float] = mapped_column(Float, default=1)  # 100 for %, 1000 for rates per 1,000
    unit: Mapped[str] = mapped_column(String(40), default="")
    target: Mapped[float] = mapped_column(Float)
    amber: Mapped[float | None] = mapped_column(Float, nullable=True)  # watch threshold
    direction: Mapped[str] = mapped_column(String(8), default="higher")  # higher | lower is better
    frequency: Mapped[str] = mapped_column(String(12), default="Monthly")
    source: Mapped[str] = mapped_column(String(200), default="")
    auto: Mapped[str] = mapped_column(String(30), default="")  # '' = manual entry; else calculated from records
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class IndicatorValue(Scoped, Base):
    __tablename__ = "indicator_values"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    indicator_id: Mapped[str] = mapped_column(String(32), index=True)
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    numerator: Mapped[float] = mapped_column(Float)
    denominator: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(Text, default="")
    entered_by: Mapped[str] = mapped_column(String(200), default="")
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# ---------------- feedback channels and committee reports
class FeedbackChannel(Scoped, Base):
    """A printable QR code for a ward or clinic that opens the same feedback form."""
    __tablename__ = "feedback_channels"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    token: Mapped[str] = mapped_column(String(24), unique=True, index=True, default=lambda: uuid.uuid4().hex[:12])
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10), default="ward")  # ward | clinic
    department_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CommitteeReport(Scoped, Base):
    __tablename__ = "committee_reports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    period: Mapped[str] = mapped_column(String(7), unique=True)
    cover_note: Mapped[str] = mapped_column(Text, default="")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_by: Mapped[str] = mapped_column(String(200), default="")

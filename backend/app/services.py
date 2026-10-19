import smtplib
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit
from .config import settings as cfg
from .defaults import DEFAULTS_FOR_SEED as DEFAULTS
from .defaults import ELEMENT_STATUSES, SENTINEL_HARM
from .ai.incident import suggest as suggest_incident
from .models import AuditLog, Capa, Case, StandardElement, CaseEvent, EmailLog, Incident, IncidentEvent, Message, Notification, Setting, Tenant, User, now


def get_setting(db: Session, key: str, tenant="t1"):
    row = db.get(Setting, (tenant, key))
    return row.value if row else DEFAULTS[key]


def put_setting(db: Session, key: str, value, tenant="t1"):
    row = db.get(Setting, (tenant, key))
    if row:
        row.value = value
    else:
        db.add(Setting(tenant_id=tenant, key=key, value=value))


def branding(db: Session):
    t = db.get(Tenant, "t1")
    return {"hospital": t.name, **t.branding, "timezone": (t.profile or {}).get("timezone", "Asia/Muscat")}


def hospital_tz(db: Session) -> ZoneInfo:
    t = db.get(Tenant, "t1")
    return ZoneInfo((t.profile or {}).get("timezone", "Asia/Muscat") if t else "Asia/Muscat")


def day_bounds(db: Session, date_from: str | None, date_to: str | None):
    """YYYY-MM-DD (hospital local dates, inclusive) -> aware UTC [start, end) datetimes or None."""
    tz = hospital_tz(db)
    try:
        start = datetime.combine(date.fromisoformat(date_from), time.min, tz) if date_from else None
        end = datetime.combine(date.fromisoformat(date_to) + timedelta(days=1), time.min, tz) if date_to else None
    except ValueError:
        raise HTTPException(422, "Dates must be written as YYYY-MM-DD.")
    return start, end


def send_email(db: Session, to: str, subject: str, body: str):
    sender = branding(db).get("sender_name", "Antier Healthcare Suite")
    status = "logged"
    if cfg.smtp_host:
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"], msg["To"] = subject, to
            msg["From"] = f"{sender} <{cfg.smtp_from.split('<')[-1].rstrip('>')}>"
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as s:
                s.starttls()
                if cfg.smtp_user:
                    s.login(cfg.smtp_user, cfg.smtp_password)
                s.send_message(msg)
            status = "sent"
        except Exception:
            status = "failed"
    db.add(EmailLog(to=to, subject=subject, body=body, status=status))


def notify(db: Session, user: User, kind: str, title: str, body: str = "", link: str = "", email=True):
    db.add(Notification(user_id=user.id, kind=kind, title=title, body=body, link=link))
    if email:
        send_email(db, user.email, f"[Antier Healthcare Suite] {title}", f"{body}\n\n{cfg.public_web_url}{link}")


def users_with_role(db: Session, role_id: str):
    return db.scalars(select(User).where(User.role_id == role_id, User.active.is_(True))).all()


def owner_for_department(db: Session, dept_id: str | None) -> User | None:
    for u in users_with_role(db, "department_head"):
        if dept_id in (u.department_ids or []):
            return u
    pro = users_with_role(db, "patient_relations")
    return pro[0] if pro else None


def next_case_number(db: Session) -> str:
    n = db.scalar(select(Case.number).order_by(Case.number.desc()).limit(1))
    return f"CS-{(int(n.split('-')[1]) + 1) if n else 1001}"


def open_case(db: Session, fb, title: str, urgency: str, dept_id: str | None, actor: User | None = None):
    sla = get_setting(db, "sla")
    due = now() + timedelta(hours=sla.get(urgency, 72))
    owner = owner_for_department(db, dept_id)
    c = Case(number=next_case_number(db), feedback_id=fb.id, patient_id=fb.patient_id, department_id=dept_id,
             title=title[:300], urgency=urgency, status="Assigned" if owner else "New",
             owner_id=owner.id if owner else None, due_at=due)
    db.add(c)
    db.flush()
    db.add(CaseEvent(case_id=c.id, kind="created", text=f"Case opened from feedback (rating {fb.rating}/5)"))
    if owner:
        db.add(CaseEvent(case_id=c.id, kind="assigned", text=f"Assigned to {owner.name}"))
        notify(db, owner, "assignment", f"Case {c.number} assigned to you", title, f"/cases/{c.id}")
    fb.case_id = c.id
    audit.log(db, actor, "cases", "create", "case", c.id, f"Case {c.number} opened", None, {"urgency": urgency, "due_at": due.isoformat()})
    return c


def next_incident_number(db: Session) -> str:
    n = db.scalar(select(Incident.number).order_by(Incident.number.desc()).limit(1))
    return f"INC-{(int(n.split('-')[1]) + 1) if n else 2001}"


def incident_due(db: Session, harm: str):
    return now() + timedelta(hours=get_setting(db, "incident_sla").get(harm, 336))


def notify_quality(db: Session, kind: str, title: str, body: str, link: str):
    for u in users_with_role(db, "quality_manager"):
        notify(db, u, kind, title, body, link)


def create_incident(db: Session, user: User | None, description: str, occurred_at, *, category: str | None = None, harm: str | None = None,
                    department_id: str | None = None, location: str = "", immediate_action: str = "", anonymous: bool = False,
                    patient_id: str | None = None, case_id: str | None = None, title: str | None = None) -> Incident:
    """One place that creates an incident, whether from the report form or from a complaint case."""
    ai, status = suggest_incident(description)
    category, harm = category or ai["category"], harm or ai["harm"]
    summary = title or (ai["summary"] if status == "ok" else description.strip()[:90])
    sentinel = is_sentinel(harm)
    inc = Incident(number=next_incident_number(db), title=summary[:300], description=description.strip(), category=category, harm=harm,
                   department_id=department_id, location=location.strip(), occurred_at=occurred_at, immediate_action=immediate_action.strip(),
                   anonymous=anonymous, reported_by=None if anonymous or not user else user.id, due_at=incident_due(db, harm), sentinel=sentinel,
                   patient_id=patient_id, case_id=case_id, ai=ai | {"status": status})
    db.add(inc)
    db.flush()
    who = "Anonymous reporter" if anonymous or not user else user.name
    db.add(IncidentEvent(incident_id=inc.id, kind="reported", text="Incident reported" + (" (serious event)" if sentinel else ""), actor=who))
    db.add(AuditLog(user_id=None if anonymous or not user else user.id, user_name=who, module="incidents", action="create", record_type="incident",
                    record_id=inc.id, summary=f"Incident {inc.number} reported", after={"category": category, "harm": harm, "sentinel": sentinel}))
    label = "Serious event" if sentinel else "New incident"
    for q in users_with_role(db, "quality_manager"):
        notify(db, q, "incident", f"{label} {inc.number}: {inc.title}", inc.description[:300], f"/quality/incidents/{inc.id}", email=sentinel)
    return inc


def check_incident_deadlines(db: Session):
    """Overdue investigations and corrective actions, each reported once."""
    n = 0
    for i in db.scalars(select(Incident).where(Incident.status != "Closed", Incident.due_at < now(), Incident.breach_notified.is_(False))):
        targets = users_with_role(db, "quality_manager")
        if i.investigator_id and (inv := db.get(User, i.investigator_id)):
            targets.append(inv)
        for u in targets:
            notify(db, u, "incident_overdue", f"Investigation overdue: {i.number}", i.title, f"/quality/incidents/{i.id}")
        db.add(IncidentEvent(incident_id=i.id, kind="escalated", text="Investigation deadline passed; Quality team notified"))
        i.breach_notified = True
        audit.log(db, None, "incidents", "overdue", "incident", i.id, f"Investigation overdue on {i.number}")
        n += 1
    for c in db.scalars(select(Capa).where(Capa.status != "Completed", Capa.due_at < now(), Capa.overdue_notified.is_(False))):
        inc = db.get(Incident, c.incident_id)
        for u in ([db.get(User, c.owner_id)] if c.owner_id else []) + users_with_role(db, "quality_manager"):
            if u:
                notify(db, u, "capa_overdue", f"Corrective action overdue on {inc.number}", c.action[:200], f"/quality/incidents/{inc.id}")
        c.overdue_notified = True
        audit.log(db, None, "incidents", "capa_overdue", "capa", c.id, f"Action overdue on {inc.number}")
        n += 1
    db.commit()
    return n


def is_sentinel(harm: str) -> bool:
    return harm in SENTINEL_HARM


def check_sla(db: Session):
    """Called by the scheduler. Raises notification + email and escalates to Quality Manager."""
    esc = get_setting(db, "escalation")
    cases = db.scalars(select(Case).where(Case.status.notin_(["Resolved", "Closed"]), Case.due_at < now(), Case.breach_notified.is_(False))).all()
    for c in cases:
        targets = users_with_role(db, esc.get("sla_breach", "quality_manager"))
        if c.owner_id and (o := db.get(User, c.owner_id)):
            targets.append(o)
        for u in targets:
            notify(db, u, "sla_breach", f"SLA breached on case {c.number}", c.title, f"/cases/{c.id}")
        db.add(CaseEvent(case_id=c.id, kind="escalated", text="SLA breached; escalated to Quality Manager"))
        c.breach_notified = True
        audit.log(db, None, "cases", "escalate", "case", c.id, f"SLA breach on {c.number}")
    db.commit()
    return len(cases) + check_incident_deadlines(db)


def whatsapp_send(db: Session, patient, body: str, language: str, link: str = "", channel: str = "whatsapp"):
    db.add(Message(patient_id=patient.id, direction="out", body=body, language=language, link=link, channel=channel))


# ---------------- accreditation readiness
def readiness(db: Session, chapter_id: str | None = None) -> dict:
    """Elements met out of applicable elements, overall or for one chapter."""
    stmt = select(StandardElement.status, func.count()).group_by(StandardElement.status)
    if chapter_id:
        stmt = stmt.where(StandardElement.chapter_id == chapter_id)
    counts = {s: 0 for s in ELEMENT_STATUSES}
    counts.update({k: v for k, v in db.execute(stmt)})
    applicable = sum(v for k, v in counts.items() if k != "Not applicable")
    return {"counts": counts, "met": counts["Met"], "applicable": applicable, "pct": round(100 * counts["Met"] / applicable, 1) if applicable else 0}

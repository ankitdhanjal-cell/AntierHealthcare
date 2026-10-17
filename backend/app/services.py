import smtplib
from datetime import timedelta
from email.mime.text import MIMEText

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .config import settings as cfg
from .defaults import DEFAULTS_FOR_SEED as DEFAULTS
from .models import Case, CaseEvent, EmailLog, Message, Notification, Setting, Tenant, User, now


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
    return {"hospital": t.name, **t.branding}


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
    return len(cases)


def whatsapp_send(db: Session, patient, body: str, language: str, link: str = ""):
    db.add(Message(patient_id=patient.id, direction="out", body=body, language=language, link=link))

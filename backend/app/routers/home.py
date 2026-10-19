from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..defaults import HARM_LEVELS
from ..indicators_calc import completed_periods, rag, series
from ..models import (AuditRun, AuditTemplate, Capa, Case, CaseCall, Department, Evidence, FeedbackResponse, Incident, Indicator, QualityAction,
                      StandardElement, User, now)
from ..security import can, current_user, dept_scope
from ..services import hospital_tz
from .accreditation import summary as accreditation_summary

router = APIRouter(prefix="/api", tags=["home"])


def task(kind: str, title: str, href: str, due: datetime | None, detail: str = ""):
    return {"kind": kind, "title": title, "href": href, "due_at": due, "overdue": bool(due and due < now()), "detail": detail}


@router.get("/tasks")
def tasks(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Everything assigned to me, soonest first. Only modules the role can open are included."""
    out = []
    if can(user, "cases"):
        for c in db.scalars(select(Case).where(Case.owner_id == user.id, Case.status.notin_(["Resolved", "Closed"]))):
            out.append(task("Case", f"{c.number} · {c.title}", f"/cases/{c.id}", c.due_at, c.urgency + " urgency"))
    if can(user, "incidents"):
        for i in db.scalars(select(Incident).where(Incident.investigator_id == user.id, Incident.status != "Closed")):
            out.append(task("Incident", f"{i.number} · {i.title}", f"/quality/incidents/{i.id}", i.due_at, "Investigation"))
        for c, i in db.execute(select(Capa, Incident).join(Incident, Incident.id == Capa.incident_id).where(Capa.owner_id == user.id)):
            if c.status != "Completed":
                out.append(task("Corrective action", f"{c.action[:110]}", f"/quality/incidents/{i.id}", c.due_at, i.number))
            elif not c.check_result and c.check_due_at and c.check_due_at < now() + timedelta(days=14):
                out.append(task("Effectiveness check", f"{c.action[:110]}", f"/quality/incidents/{i.id}", c.check_due_at, i.number))
    if can(user, "audits"):
        tpls = {t.id: t.name for t in db.scalars(select(AuditTemplate))}
        for r in db.scalars(select(AuditRun).where(AuditRun.auditor_id == user.id, AuditRun.status == "Scheduled")):
            out.append(task("Audit", f"{tpls[r.template_id]} · {r.unit} {r.period}", f"/quality/audits/runs/{r.id}", r.due_at))
    if can(user, "accreditation"):
        for a in db.scalars(select(QualityAction).where(QualityAction.owner_id == user.id, QualityAction.status != "Completed")):
            out.append(task("Action", a.text[:120], f"/quality/accreditation/elements/{a.element_id}" if a.element_id else "/quality/audits", a.due_at, a.source_type))
        has_ev = set(db.scalars(select(Evidence.element_id)))
        for e in db.scalars(select(StandardElement).where(StandardElement.owner_id == user.id, StandardElement.status != "Not applicable")):
            stale = e.last_reviewed_at is None or e.last_reviewed_at < now() - timedelta(days=180)
            if stale or (e.status == "Met" and e.id not in has_ev):
                due = (e.last_reviewed_at + timedelta(days=180)) if e.last_reviewed_at else now()
                out.append(task("Evidence review", f"{e.code} · {e.text[:100]}", f"/quality/accreditation/elements/{e.id}", due, "review due" if stale else "no evidence attached"))
    out.sort(key=lambda t: (t["due_at"] is None, t["due_at"] or now()))
    return {"total": len(out), "overdue": sum(t["overdue"] for t in out), "items": out[:30]}


def open_cases(user: User, scope):
    stmt = select(Case).where(Case.status.notin_(["Resolved", "Closed"]))
    return stmt.where(Case.department_id.in_(scope)) if scope is not None else stmt


@router.get("/home")
def home(db: Session = Depends(get_db), user: User = Depends(current_user)):
    role, scope = user.role_id, dept_scope(user)
    tz = hospital_tz(db)
    start_today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = start_today + timedelta(days=1)
    if role in ("quality_manager", "admin", "management_viewer") and can(user, "accreditation"):
        acc = accreditation_summary(db, user)
        harm = dict(HARM_LEVELS)
        incs = db.scalars(select(Incident).where(Incident.status != "Closed")).all()
        n = lambda stmt: db.scalar(select(func.count()).select_from(stmt.subquery()))
        periods = completed_periods(12)
        off = []
        for ind in db.scalars(select(Indicator).order_by(Indicator.position)):
            pts = series(db, ind, periods)
            if pts and rag(ind, pts[-1]["value"]) == "red":
                off.append({"id": ind.id, "name": ind.name, "value": pts[-1]["value"], "unit": ind.unit, "key": ind.key})
        return {"kind": "quality", "readiness": acc["readiness"], "days_left": acc["days_left"], "survey_date": acc["survey_date"], "gaps": len(acc["gaps"]),
                "counts": {"overdue_actions": n(select(Capa.id).where(Capa.status != "Completed", Capa.due_at < now())) + n(select(QualityAction.id).where(QualityAction.status != "Completed", QualityAction.due_at < now())),
                           "overdue_incidents": sum(i.due_at is not None and i.due_at < now() for i in incs), "open_incidents": len(incs), "serious_open": sum(i.sentinel for i in incs),
                           "overdue_audits": n(select(AuditRun.id).where(AuditRun.status != "Completed", AuditRun.due_at < now())),
                           "cases_past_sla": n(select(Case.id).where(Case.status.notin_(["Resolved", "Closed"]), Case.due_at < now())),
                           "triage_queue": sum(i.status == "Reported" for i in incs)},
                "open_by_harm": [{"harm": k, "label": harm[k], "count": sum(i.harm == k for i in incs)} for k in harm if any(i.harm == k for i in incs)], "off_target": off}
    if role == "patient_relations":
        cases = db.scalars(open_cases(user, scope).order_by(Case.due_at).limit(12)).all()
        called = set(db.scalars(select(CaseCall.case_id)))
        every = db.scalars(open_cases(user, scope)).all()
        users = {u.id: u.name for u in db.scalars(select(User))}
        return {"kind": "patient_relations",
                "counts": {"new_today": sum(start_today <= c.created_at < end_today for c in every), "due_today": sum(start_today <= c.due_at < end_today for c in every),
                           "overdue": sum(c.due_at < now() for c in every), "awaiting_callback": sum(c.id not in called for c in every), "open": len(every),
                           "feedback_today": db.scalar(select(func.count()).select_from(FeedbackResponse).where(FeedbackResponse.created_at >= start_today, FeedbackResponse.created_at < end_today))},
                "cases": [{"id": c.id, "number": c.number, "title": c.title, "urgency": c.urgency, "status": c.status, "due_at": c.due_at, "overdue": c.due_at < now(),
                           "owner": users.get(c.owner_id, "Unassigned"), "callback_logged": c.id in called} for c in cases]}
    names = [d.name for d in db.scalars(select(Department).where(Department.id.in_(scope or [])))] if scope is not None else []
    since = now() - timedelta(days=30)
    fb = select(func.avg(FeedbackResponse.rating), func.count()).where(FeedbackResponse.created_at >= since)
    inc = select(func.count()).select_from(Incident).where(Incident.status != "Closed")
    runs = select(func.count()).select_from(AuditRun).where(AuditRun.status != "Completed")
    cs = open_cases(user, scope)
    if scope is not None:
        fb, inc, runs = fb.where(FeedbackResponse.department_id.in_(scope)), inc.where(Incident.department_id.in_(scope)), runs.where(AuditRun.department_id.in_(scope))
    avg, n_fb = db.execute(fb).one()
    cases = db.scalars(cs).all()
    return {"kind": "department", "departments": names, "scoped": scope is not None,
            "counts": {"open_cases": len(cases), "overdue_cases": sum(c.due_at < now() for c in cases), "open_incidents": db.scalar(inc) if can(user, "incidents") else None,
                       "audits_due": db.scalar(runs) if can(user, "audits") else None, "rating_30d": round(float(avg), 2) if avg else None, "responses_30d": n_fb}}

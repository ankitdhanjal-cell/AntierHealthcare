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
from ..services import day_bounds, hospital_tz
from .accreditation import summary as accreditation_summary
from .audits import scoped_runs
from .incidents import visible as visible_incidents

router = APIRouter(prefix="/api", tags=["home"])


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month_label(p: str) -> str:
    y, m = p.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


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
            out.append(task("Audit", f"{tpls[r.template_id]} · {r.unit} {month_label(r.period)}", f"/quality/audits/runs/{r.id}", r.due_at))
    if can(user, "accreditation"):
        mine = db.scalars(select(QualityAction).where(QualityAction.owner_id == user.id, QualityAction.status != "Completed")).all()
        gap_elements = {a.element_id for a in mine if a.source_type == "gap" and a.element_id}
        for a in mine:
            if a.source_type == "tracer" and a.element_id in gap_elements:
                continue  # the same gap is already listed once
            out.append(task("Action", a.text[:120], f"/quality/accreditation/elements/{a.element_id}" if a.element_id else "/quality/audits", a.due_at, a.source_type))
        has_ev = set(db.scalars(select(Evidence.element_id)))
        for e in db.scalars(select(StandardElement).where(StandardElement.owner_id == user.id, StandardElement.status != "Not applicable")):
            stale = e.last_reviewed_at is None or e.last_reviewed_at < now() - timedelta(days=180)
            if stale or (e.status == "Met" and e.id not in has_ev):
                due = (e.last_reviewed_at + timedelta(days=180)) if e.last_reviewed_at else now()
                out.append(task("Evidence review", f"{e.code} · {e.text[:100]}", f"/quality/accreditation/elements/{e.id}", due, "review due" if stale else "no evidence attached"))
    seen, unique = set(), []
    for t in out:
        key = (t["kind"], t["title"])
        if key not in seen:
            seen.add(key)
            unique.append(t)
    out = unique
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
    if role == "management_viewer":
        return management_home(db, user)
    if role == "infection_control":
        return audit_home(db, user, scope)
    if role == "staff_reporter":
        return reporter_home(db, user)
    if role in ("quality_manager", "admin") and can(user, "accreditation"):
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
                "links": {"overdue_actions": "/quality/actions?overdue=true", "cases_past_sla": "/cases?overdue=true", "open_incidents": "/quality/incidents?open=true",
                          "serious_open": "/quality/incidents?sentinel=true&open=true", "overdue_incidents": "/quality/incidents?overdue=true", "overdue_audits": "/quality/audits?overdue=true",
                          "triage_queue": "/quality/incidents?status=Reported"},
                "open_by_harm": [{"harm": k, "label": harm[k], "count": sum(i.harm == k for i in incs)} for k in harm if any(i.harm == k for i in incs)], "off_target": off}
    if role == "patient_relations":
        cases = db.scalars(open_cases(user, scope).order_by(Case.due_at).limit(12)).all()
        called = set(db.scalars(select(CaseCall.case_id)))
        every = db.scalars(open_cases(user, scope)).all()
        users = {u.id: u.name for u in db.scalars(select(User))}
        today = start_today.date().isoformat()
        return {"kind": "patient_relations", "today": today,
                "links": {"new_today": f"/cases?open=true&date_from={today}&date_to={today}", "due_today": f"/cases?open=true&due_from={today}&due_to={today}", "overdue": "/cases?overdue=true",
                          "awaiting_callback": "/cases?open=true&no_call=true", "open": "/cases?open=true", "feedback_today": f"/feedback?date_from={today}&date_to={today}"},
                "counts": {"new_today": sum(start_today <= c.created_at < end_today for c in every), "due_today": sum(start_today <= c.due_at < end_today for c in every),
                           "overdue": sum(c.due_at < now() for c in every), "awaiting_callback": sum(c.id not in called for c in every), "open": len(every),
                           "feedback_today": db.scalar(select(func.count()).select_from(FeedbackResponse).where(FeedbackResponse.created_at >= start_today, FeedbackResponse.created_at < end_today))},
                "cases": [{"id": c.id, "number": c.number, "title": c.title, "urgency": c.urgency, "status": c.status, "due_at": c.due_at, "overdue": c.due_at < now(),
                           "owner": users.get(c.owner_id, "Unassigned"), "callback_logged": c.id in called} for c in cases]}
    names = [d.name for d in db.scalars(select(Department).where(Department.id.in_(scope or [])))] if scope is not None else []
    since_date = (datetime.now(tz) - timedelta(days=30)).date().isoformat()
    since = day_bounds(db, since_date, None)[0]  # same start as the link, so the figure and the list agree
    fb = select(func.avg(FeedbackResponse.rating), func.count()).where(FeedbackResponse.created_at >= since)
    inc = visible_incidents(select(func.count()).select_from(Incident).where(Incident.status != "Closed"), user)
    runs = scoped_runs(select(func.count()).select_from(AuditRun).where(AuditRun.status != "Completed"), user)
    cs = open_cases(user, scope)
    if scope is not None:
        fb = fb.where(FeedbackResponse.department_id.in_(scope))
    avg, n_fb = db.execute(fb).one()
    cases = db.scalars(cs).all()
    return {"kind": "department", "departments": names, "scoped": scope is not None, "can_dashboard": can(user, "dashboard"),
            "links": {"open_cases": "/cases?open=true", "overdue_cases": "/cases?overdue=true", "open_incidents": "/quality/incidents?open=true", "audits_due": "/quality/audits?status=Scheduled",
                      "rating_30d": f"/feedback?date_from={since_date}"},
            "counts": {"open_cases": len(cases), "overdue_cases": sum(c.due_at < now() for c in cases), "open_incidents": db.scalar(inc) if can(user, "incidents") else None,
                       "audits_due": db.scalar(runs) if can(user, "audits") else None, "rating_30d": round(float(avg), 2) if avg else None, "responses_30d": n_fb}}


def indicator_rows(db, keys=None):
    periods, rows = completed_periods(12), []
    for ind in db.scalars(select(Indicator).order_by(Indicator.position)):
        if keys and ind.key not in keys:
            continue
        pts = series(db, ind, periods)
        rows.append({"id": ind.id, "key": ind.key, "name": ind.name, "unit": ind.unit, "target": ind.target, "direction": ind.direction,
                     "value": pts[-1]["value"] if pts else None, "period": pts[-1]["period"] if pts else None, "rag": rag(ind, pts[-1]["value"] if pts else None),
                     "spark": [p["value"] for p in pts]})
    return rows


def management_home(db, user):
    """One page for a senior reader: readiness, serious events, indicators against target and the patient trend."""
    acc = accreditation_summary(db, user)
    inds = indicator_rows(db)
    sat = next((i for i in inds if i["key"] == "satisfaction"), None)
    serious = db.scalars(select(Incident).where(Incident.sentinel.is_(True), Incident.status != "Closed")).all()
    return {"kind": "management", "readiness": acc["readiness"], "days_left": acc["days_left"], "survey_date": acc["survey_date"], "gaps": len(acc["gaps"]),
            "serious": [{"id": i.id, "number": i.number, "title": i.title, "status": i.status, "escalated": bool(i.escalated_at)} for i in serious],
            "indicators": inds, "on_target": sum(i["rag"] == "green" for i in inds), "off_target": sum(i["rag"] == "red" for i in inds), "watch": sum(i["rag"] == "amber" for i in inds),
            "satisfaction": sat}


def audit_home(db, user, scope):
    """Infection control: audits due, compliance against target and the infection indicators first."""
    tpls = {t.id: t for t in db.scalars(select(AuditTemplate))}
    runs = db.scalars(scoped_runs(select(AuditRun), user)).all()
    due = sorted([r for r in runs if r.status != "Completed"], key=lambda r: r.due_at)
    comp = []
    for t in tpls.values():
        done = [r for r in runs if r.template_id == t.id and r.status == "Completed"]
        if not done:
            continue
        latest = max(r.period for r in done)
        rs = [r for r in done if r.period == latest]
        yes, no = sum(r.yes_count for r in rs), sum(r.no_count for r in rs)
        if yes + no:
            comp.append({"id": t.id, "name": t.name, "period": latest, "score": round(100 * yes / (yes + no), 1), "target": t.target, "audits": len(rs)})
    names = [d.name for d in db.scalars(select(Department).where(Department.id.in_(scope or [])))] if scope is not None else []
    return {"kind": "audit", "departments": names, "counts": {"due": len(due), "overdue": sum(r.due_at < now() for r in due), "completed": len(runs) - len(due),
                                                              "below_target": sum(c["score"] < c["target"] for c in comp)},
            "links": {"due": "/quality/audits?status=Scheduled", "overdue": "/quality/audits?overdue=true", "mine": "/quality/audits?mine=true"},
            "compliance": comp, "indicators": indicator_rows(db, {"hand_hygiene", "hai_rate"}),
            "next": [{"id": r.id, "template": tpls[r.template_id].name, "unit": r.unit, "period": month_label(r.period), "due_at": r.due_at, "overdue": r.due_at < now()} for r in due[:8]]}


def reporter_home(db, user):
    """A reporting-only role: their own reports and where each one stands."""
    mine = db.scalars(select(Incident).where(Incident.reported_by == user.id).order_by(Incident.created_at.desc())).all()
    by = {}
    for i in mine:
        by[i.status] = by.get(i.status, 0) + 1
    return {"kind": "reporter", "counts": {"total": len(mine), "open": sum(i.status != "Closed" for i in mine), "closed": by.get("Closed", 0)}, "by_status": by,
            "reports": [{"id": i.id, "number": i.number, "title": i.title, "status": i.status, "created_at": i.created_at, "harm": i.harm} for i in mine[:12]]}

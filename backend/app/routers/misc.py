import csv
import io
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..connectors.sandbox import CARDS, his, whatsapp
from ..db import get_db
from ..models import (AuditLog, Case, EmailLog, FeedbackResponse, Message, Notification, Patient, User, now)
from ..security import dept_scope, require
from ..services import get_setting

router = APIRouter(prefix="/api", tags=["misc"])


# ---------- notifications
@router.get("/notifications")
def notifications(db: Session = Depends(get_db), u: User = Depends(require("dashboard"))):
    items = db.scalars(select(Notification).where(Notification.user_id == u.id).order_by(Notification.created_at.desc()).limit(100)).all()
    return {"unread": sum(not n.read for n in items),
            "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": n.read, "created_at": n.created_at} for n in items]}


@router.post("/notifications/read")
def read_all(db: Session = Depends(get_db), u: User = Depends(require("dashboard"))):
    for n in db.scalars(select(Notification).where(Notification.user_id == u.id, Notification.read.is_(False))):
        n.read = True
    db.commit()
    return {"ok": True}


@router.get("/emails")
def emails(db: Session = Depends(get_db), u: User = Depends(require("settings"))):
    return [{"id": e.id, "to": e.to, "subject": e.subject, "status": e.status, "created_at": e.created_at}
            for e in db.scalars(select(EmailLog).order_by(EmailLog.created_at.desc()).limit(100))]


# ---------- audit trail
def audit_query(module, user_id, record_id, q):
    stmt = select(AuditLog).order_by(AuditLog.at.desc())
    if module:
        stmt = stmt.where(AuditLog.module == module)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if record_id:
        stmt = stmt.where(AuditLog.record_id == record_id)
    if q:
        stmt = stmt.where(AuditLog.summary.ilike(f"%{q}%"))
    return stmt


@router.get("/audit")
def audit_list(page: int = 1, size: int = Query(25, le=200), module: str | None = None, user_id: str | None = None,
               record_id: str | None = None, q: str | None = None, db: Session = Depends(get_db), u: User = Depends(require("audit"))):
    stmt = audit_query(module, user_id, record_id, q)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
    return {"total": total, "items": [{"id": a.id, "at": a.at, "user": a.user_name, "module": a.module, "action": a.action,
                                        "record_type": a.record_type, "record_id": a.record_id, "summary": a.summary,
                                        "before": a.before, "after": a.after} for a in rows]}


@router.get("/audit/export")
def audit_export(module: str | None = None, user_id: str | None = None, record_id: str | None = None, q: str | None = None,
                 db: Session = Depends(get_db), u: User = Depends(require("audit"))):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["when", "user", "module", "action", "record", "summary", "before", "after"])
    for a in db.scalars(audit_query(module, user_id, record_id, q).limit(5000)):
        w.writerow([a.at.isoformat(), a.user_name, a.module, a.action, f"{a.record_type}:{a.record_id}", a.summary, a.before, a.after])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=audit-trail.csv"})


# ---------- integrations
@router.get("/integrations")
def integrations(u: User = Depends(require("integrations"))):
    return CARDS


@router.get("/integrations/his/patients")
def his_patients(db: Session = Depends(get_db), u: User = Depends(require("integrations"))):
    ps = db.scalars(select(Patient).order_by(Patient.discharged_at.desc().nullsfirst(), Patient.name).limit(40)).all()
    return [{"id": p.id, "mrn": p.mrn, "name": p.name, "language": p.language, "discharged_at": p.discharged_at} for p in ps]


class Discharge(BaseModel):
    patient_id: str
    send_now: bool = True


@router.post("/integrations/his/discharge")
def his_discharge(b: Discharge, db: Session = Depends(get_db), u: User = Depends(require("integrations", "create"))):
    p = db.get(Patient, b.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    req, hl7 = his.discharge_event(db, p, b.send_now, u)
    if b.send_now:
        whatsapp.send_feedback_request(db, req, p)
    else:
        from ..celery_app import send_request_task
        try:
            send_request_task.apply_async(args=[req.id], eta=req.send_at)
        except Exception:
            pass  # scheduler sweep will pick it up
    db.commit()
    return {"request_id": req.id, "hl7": hl7.replace("\r", "\n"), "status": req.status, "send_at": req.send_at}


@router.get("/whatsapp/messages")
def wa_messages(patient_id: str | None = None, db: Session = Depends(get_db), u: User = Depends(require("integrations"))):
    stmt = select(Message).order_by(Message.created_at.desc()).limit(30)
    if patient_id:
        stmt = stmt.where(Message.patient_id == patient_id)
    ms = list(db.scalars(stmt))[::-1]
    pats = {p.id: p.name for p in db.scalars(select(Patient).where(Patient.id.in_({m.patient_id for m in ms})))} if ms else {}
    return [{"id": m.id, "patient_id": m.patient_id, "patient": pats.get(m.patient_id, ""), "direction": m.direction,
             "body": m.body, "language": m.language, "link": m.link, "created_at": m.created_at} for m in ms]


@router.post("/admin/reset-sandbox")
def reset(db: Session = Depends(get_db), u: User = Depends(require("settings", "admin"))):
    from ..seed import rebuild
    rebuild(db)
    return {"ok": True}


# ---------- global search
@router.get("/search")
def search(q: str, db: Session = Depends(get_db), u: User = Depends(require("dashboard"))):
    if len(q) < 2:
        return []
    out = []
    scope = dept_scope(u)
    for c in db.scalars(select(Case).where(Case.title.ilike(f"%{q}%") | Case.number.ilike(f"%{q}%")).limit(6)):
        if scope is None or c.department_id in scope:
            out.append({"type": "Case", "title": f"{c.number} · {c.title}", "href": f"/cases/{c.id}"})
    fbs = db.scalars(select(FeedbackResponse).where(FeedbackResponse.text.ilike(f"%{q}%")).limit(6))
    for f in fbs:
        if scope is None or f.department_id in scope:
            out.append({"type": "Feedback", "title": (f.text or "")[:80], "href": f"/feedback/{f.id}"})
    if u.role.permissions.get("feedback"):
        masked = get_setting(db, "routing").get("mask_patient_names", False)
        if not masked:
            for p in db.scalars(select(Patient).where(Patient.name.ilike(f"%{q}%") | Patient.mrn.ilike(f"%{q}%")).limit(5)):
                out.append({"type": "Patient", "title": f"{p.name} · {p.mrn}", "href": f"/feedback?q={p.name}"})
    return out


# ---------- dashboard
@router.get("/dashboard")
def dashboard(months: int = 6, db: Session = Depends(get_db), u: User = Depends(require("dashboard"))):
    scope = dept_scope(u)
    since = now() - timedelta(days=30 * months)
    fb = select(FeedbackResponse).where(FeedbackResponse.created_at >= since)
    cs = select(Case)
    if scope is not None:
        fb = fb.where(FeedbackResponse.department_id.in_(scope))
        cs = cs.where(Case.department_id.in_(scope))
    fbs = db.scalars(fb).all()
    cases = db.scalars(cs).all()
    avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else 0
    by_month: dict[str, list] = {}
    for f in fbs:
        by_month.setdefault(f.created_at.strftime("%Y-%m"), []).append(f.rating)
    trend = [{"month": m, "rating": avg(v), "count": len(v)} for m, v in sorted(by_month.items())]
    closed = [(c.closed_at - c.created_at).total_seconds() / 3600 for c in cases if c.closed_at]
    open_cases = [c for c in cases if c.status not in ("Resolved", "Closed")]
    past = [c for c in open_cases if c.due_at < now()]
    opened_m: dict[str, int] = {}
    closed_m: dict[str, int] = {}
    for c in cases:
        opened_m[c.created_at.strftime("%Y-%m")] = opened_m.get(c.created_at.strftime("%Y-%m"), 0) + 1
        if c.closed_at:
            closed_m[c.closed_at.strftime("%Y-%m")] = closed_m.get(c.closed_at.strftime("%Y-%m"), 0) + 1
    themes: dict[str, int] = {}
    for f in fbs:
        if f.sentiment != "positive":
            for t in f.themes:
                themes[t] = themes.get(t, 0) + 1
    kpi_defs = {k["key"]: k for k in get_setting(db, "kpis")}

    def rag(key, val):
        k = kpi_defs.get(key)
        if not k:
            return "neutral"
        if k["direction"] == "higher":
            return "green" if val >= k["target"] else "amber" if val >= k["amber"] else "red"
        return "green" if val <= k["target"] else "amber" if val <= k["amber"] else "red"

    sat, clo = avg([f.rating for f in fbs]), avg(closed)
    sentiments = {s: sum(f.sentiment == s for f in fbs) for s in ("positive", "neutral", "negative")}
    return {
        "kpis": [
            {"key": "satisfaction", "label": "Patient satisfaction", "value": sat, "unit": "/ 5", "target": kpi_defs.get("satisfaction", {}).get("target"), "rag": rag("satisfaction", sat)},
            {"key": "closure_time", "label": "Avg complaint closure time", "value": clo, "unit": "h", "target": kpi_defs.get("closure_time", {}).get("target"), "rag": rag("closure_time", clo)},
            {"key": "cases_past_sla", "label": "Cases past SLA", "value": len(past), "unit": "", "target": kpi_defs.get("cases_past_sla", {}).get("target"), "rag": rag("cases_past_sla", len(past))},
            {"key": "open_cases", "label": "Open cases", "value": len(open_cases), "unit": "", "target": None, "rag": "neutral"},
        ],
        "satisfaction_trend": trend,
        "cases_trend": [{"month": m, "opened": opened_m.get(m, 0), "closed": closed_m.get(m, 0)} for m in sorted(set(opened_m) | set(closed_m)) if m >= since.strftime("%Y-%m")],
        "sentiment": sentiments,
        "top_themes": sorted([{"theme": k, "count": v} for k, v in themes.items()], key=lambda x: -x["count"])[:6],
        "overdue_cases": [{"id": c.id, "number": c.number, "title": c.title, "due_at": c.due_at} for c in sorted(past, key=lambda c: c.due_at)[:8]],
        "responses": len(fbs),
    }

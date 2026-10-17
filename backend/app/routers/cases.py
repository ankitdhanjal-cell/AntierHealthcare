from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Case, CaseEvent, Department, FeedbackResponse, Patient, User, now
from ..security import dept_scope, require
from ..services import get_setting, notify

router = APIRouter(prefix="/api/cases", tags=["cases"])
STATUSES = ["New", "Assigned", "In investigation", "Resolved", "Closed"]


def case_row(c: Case, users: dict, depts: dict):
    overdue = c.status not in ("Resolved", "Closed") and c.due_at < now()
    return {"id": c.id, "number": c.number, "title": c.title, "urgency": c.urgency, "status": c.status,
            "owner_id": c.owner_id, "owner": users.get(c.owner_id, "Unassigned"), "department": depts.get(c.department_id, "—"),
            "department_id": c.department_id, "due_at": c.due_at, "created_at": c.created_at, "closed_at": c.closed_at,
            "overdue": overdue, "feedback_id": c.feedback_id, "incident_id": c.incident_id}


def maps(db):
    return ({u.id: u.name for u in db.scalars(select(User))}, {d.id: d.name for d in db.scalars(select(Department))})


@router.get("")
def list_cases(page: int = 1, size: int = Query(20, le=100), sort: str = "created_at", order: str = "desc",
               status: str | None = None, urgency: str | None = None, department_id: str | None = None,
               owner_id: str | None = None, overdue: bool | None = None, q: str | None = None,
               db: Session = Depends(get_db), user: User = Depends(require("cases"))):
    stmt = select(Case)
    scope = dept_scope(user)
    if scope is not None:
        stmt = stmt.where(Case.department_id.in_(scope))
    if status:
        stmt = stmt.where(Case.status == status)
    if urgency:
        stmt = stmt.where(Case.urgency == urgency)
    if department_id:
        stmt = stmt.where(Case.department_id == department_id)
    if owner_id:
        stmt = stmt.where(Case.owner_id == owner_id)
    if overdue:
        stmt = stmt.where(Case.status.notin_(["Resolved", "Closed"]), Case.due_at < now())
    if q:
        stmt = stmt.where(Case.title.ilike(f"%{q}%") | Case.number.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = getattr(Case, sort if sort in ("created_at", "due_at", "status", "urgency", "number") else "created_at")
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc()).offset((page - 1) * size).limit(size)
    users, depts = maps(db)
    return {"total": total, "items": [case_row(c, users, depts) for c in db.scalars(stmt)]}


def get_case(db, cid, user):
    c = db.get(Case, cid)
    scope = dept_scope(user)
    if not c or (scope is not None and c.department_id not in scope):
        raise HTTPException(404, "Case not found")
    return c


@router.get("/{cid}")
def detail(cid: str, db: Session = Depends(get_db), user: User = Depends(require("cases"))):
    c = get_case(db, cid, user)
    users, depts = maps(db)
    fb = db.get(FeedbackResponse, c.feedback_id) if c.feedback_id else None
    p = db.get(Patient, c.patient_id)
    events = db.scalars(select(CaseEvent).where(CaseEvent.case_id == c.id).order_by(CaseEvent.created_at)).all()
    masked = get_setting(db, "routing").get("mask_patient_names", False)
    name = " ".join(w[0] + "***" for w in p.name.split()) if masked else p.name
    return case_row(c, users, depts) | {
        "patient": name, "resolution": c.resolution,
        "feedback": {"id": fb.id, "rating": fb.rating, "text": fb.text, "summary": (fb.ai or {}).get("summary", ""),
                     "translation": (fb.ai or {}).get("translation_en", ""), "themes": fb.themes, "language": fb.language} if fb else None,
        "timeline": [{"kind": e.kind, "text": e.text, "actor": e.actor, "at": e.created_at} for e in events],
        "sla_hours": get_setting(db, "sla").get(c.urgency)}


class Assign(BaseModel):
    owner_id: str


def _assign(db, c, owner: User, actor: User):
    before = {"owner_id": c.owner_id, "status": c.status}
    c.owner_id = owner.id
    if c.status == "New":
        c.status = "Assigned"
    db.add(CaseEvent(case_id=c.id, kind="assigned", text=f"Assigned to {owner.name}", actor=actor.name))
    notify(db, owner, "assignment", f"Case {c.number} assigned to you", c.title, f"/cases/{c.id}")
    audit.log(db, actor, "cases", "assign", "case", c.id, f"{c.number} assigned to {owner.name}", before, {"owner_id": owner.id, "status": c.status})


@router.post("/{cid}/assign")
def assign(cid: str, b: Assign, db: Session = Depends(get_db), user: User = Depends(require("cases", "approve"))):
    c = get_case(db, cid, user)
    owner = db.get(User, b.owner_id)
    if not owner:
        raise HTTPException(404, "User not found")
    _assign(db, c, owner, user)
    db.commit()
    return {"ok": True}


class StatusBody(BaseModel):
    status: str
    resolution: str = ""


@router.post("/{cid}/status")
def set_status(cid: str, b: StatusBody, db: Session = Depends(get_db), user: User = Depends(require("cases", "create"))):
    c = get_case(db, cid, user)
    if b.status not in STATUSES:
        raise HTTPException(422, "Invalid status")
    if b.status in ("Resolved", "Closed") and not (b.resolution or c.resolution):
        raise HTTPException(422, "A resolution note is required to resolve or close a case.")
    before = {"status": c.status}
    c.status = b.status
    if b.resolution:
        c.resolution = b.resolution
    if b.status in ("Resolved", "Closed") and not c.closed_at:
        c.closed_at = now()
    db.add(CaseEvent(case_id=c.id, kind="status", text=f"Status changed to {b.status}" + (f": {b.resolution}" if b.resolution else ""), actor=user.name))
    audit.log(db, user, "cases", "status", "case", c.id, f"{c.number} → {b.status}", before, {"status": b.status})
    db.commit()
    return {"ok": True}


class Note(BaseModel):
    text: str


@router.post("/{cid}/notes")
def add_note(cid: str, b: Note, db: Session = Depends(get_db), user: User = Depends(require("cases", "create"))):
    c = get_case(db, cid, user)
    if not b.text.strip():
        raise HTTPException(422, "Note cannot be empty.")
    db.add(CaseEvent(case_id=c.id, kind="note", text=b.text.strip(), actor=user.name))
    audit.log(db, user, "cases", "note", "case", c.id, f"Note added to {c.number}")
    db.commit()
    return {"ok": True}


class BulkBody(BaseModel):
    ids: list[str]
    owner_id: str | None = None
    close: bool = False
    resolution: str = ""


@router.post("/bulk")
def bulk(b: BulkBody, db: Session = Depends(get_db), user: User = Depends(require("cases", "approve"))):
    cases = [get_case(db, i, user) for i in b.ids]
    if b.close and not b.resolution.strip():
        raise HTTPException(422, "A resolution note is required to close cases.")
    owner = db.get(User, b.owner_id) if b.owner_id else None
    for c in cases:
        if owner:
            _assign(db, c, owner, user)
        if b.close:
            c.status, c.resolution, c.closed_at = "Closed", b.resolution, c.closed_at or now()
            db.add(CaseEvent(case_id=c.id, kind="closed", text=f"Closed: {b.resolution}", actor=user.name))
            audit.log(db, user, "cases", "status", "case", c.id, f"{c.number} closed (bulk)")
    db.commit()
    return {"updated": len(cases)}

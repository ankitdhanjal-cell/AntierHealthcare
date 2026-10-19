from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Case, CaseCall, CaseEvent, Department, FeedbackResponse, Incident, IncidentEvent, Patient, User, now
from ..connectors.sandbox import whatsapp
from ..security import can, dept_scope, require
from ..services import create_incident, day_bounds, get_setting, notify

router = APIRouter(prefix="/api/cases", tags=["cases"])
STATUSES = ["New", "Assigned", "In investigation", "Resolved", "Closed"]


LOOP_OUTCOMES = ("reached", "apologised", "resolved")


def loop_ids(db) -> set:
    """Cases where the patient was actually spoken to (reached, apologised or resolved on the call)."""
    return set(db.scalars(select(CaseCall.case_id).where(CaseCall.outcome.in_(LOOP_OUTCOMES))))


def case_row(c: Case, users: dict, depts: dict, loops: frozenset | set = frozenset()):
    overdue = c.status not in ("Resolved", "Closed") and c.due_at < now()
    return {"id": c.id, "number": c.number, "title": c.title, "urgency": c.urgency, "status": c.status,
            "owner_id": c.owner_id, "owner": users.get(c.owner_id, "Unassigned"), "department": depts.get(c.department_id, "—"),
            "department_id": c.department_id, "due_at": c.due_at, "created_at": c.created_at, "closed_at": c.closed_at,
            "overdue": overdue, "feedback_id": c.feedback_id, "incident_id": c.incident_id,
            "loop_closed": c.status in ("Resolved", "Closed") and c.id in loops, "closing_message_at": c.closing_message_at}


def maps(db):
    return ({u.id: u.name for u in db.scalars(select(User))}, {d.id: d.name for d in db.scalars(select(Department))})


@router.get("")
def list_cases(page: int = 1, size: int = Query(20, le=100), sort: str = "created_at", order: str = "desc",
               status: str | None = None, urgency: str | None = None, department_id: str | None = None,
               owner_id: str | None = None, overdue: bool | None = None, open: bool | None = None, closed: bool | None = None, loop: str | None = None,
               date_from: str | None = None, date_to: str | None = None, closed_from: str | None = None, closed_to: str | None = None,
               due_from: str | None = None, due_to: str | None = None, no_call: bool | None = None, q: str | None = None,
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
    if open:
        stmt = stmt.where(Case.status.notin_(["Resolved", "Closed"]))
    if closed:
        stmt = stmt.where(Case.closed_at.isnot(None))
    if loop in ("closed", "open"):  # service recovery: was the patient called back?
        done = select(CaseCall.case_id).where(CaseCall.outcome.in_(LOOP_OUTCOMES))
        stmt = stmt.where(Case.status.in_(["Resolved", "Closed"]), Case.id.in_(done) if loop == "closed" else Case.id.notin_(done))
    start, end = day_bounds(db, date_from, date_to)
    if start:
        stmt = stmt.where(Case.created_at >= start)
    if end:
        stmt = stmt.where(Case.created_at < end)
    d_start, d_end = day_bounds(db, due_from, due_to)
    if d_start:
        stmt = stmt.where(Case.due_at >= d_start)
    if d_end:
        stmt = stmt.where(Case.due_at < d_end)
    if no_call:  # service recovery: nobody has called the patient yet
        stmt = stmt.where(Case.id.notin_(select(CaseCall.case_id)))
    c_start, c_end = day_bounds(db, closed_from, closed_to)
    if c_start:
        stmt = stmt.where(Case.closed_at >= c_start)
    if c_end:
        stmt = stmt.where(Case.closed_at < c_end)
    if q:
        stmt = stmt.where(Case.title.ilike(f"%{q}%") | Case.number.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = getattr(Case, sort if sort in ("created_at", "due_at", "status", "urgency", "number") else "created_at")
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc()).offset((page - 1) * size).limit(size)
    users, depts = maps(db)
    loops = loop_ids(db)
    return {"total": total, "items": [case_row(c, users, depts, loops) for c in db.scalars(stmt)]}


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
    return case_row(c, users, depts, loop_ids(db)) | {
        "patient": name, "resolution": c.resolution,
        "feedback": {"id": fb.id, "rating": fb.rating, "text": fb.text, "summary": (fb.ai or {}).get("summary", ""),
                     "translation": (fb.ai or {}).get("translation_en", ""), "themes": fb.themes, "language": fb.language} if fb else None,
        "incident": ({"id": inc.id, "number": inc.number} if (inc := db.get(Incident, c.incident_id)) else None) if c.incident_id else None,
        "timeline": [{"kind": e.kind, "text": e.text, "actor": e.actor, "at": e.created_at} for e in events],
        "sla_hours": get_setting(db, "sla").get(c.urgency)}


class Assign(BaseModel):
    owner_id: str


@router.get("/meta/assignees")
def assignees(db: Session = Depends(get_db), user: User = Depends(require("cases", "approve"))):
    """People who can act on a case: active users whose role may update cases."""
    out = []
    for u in db.scalars(select(User).where(User.active.is_(True)).order_by(User.name)):
        if can(u, "cases", "create"):
            out.append({"id": u.id, "name": u.name, "role": u.role.name})
    return out


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
    if not owner or not can(owner, "cases", "create"):
        raise HTTPException(422, "Choose someone whose role can work on cases.")
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


CALL_OUTCOMES = {"reached": "Patient reached", "apologised": "Apologised to patient", "resolved": "Resolved on the call",
                 "follow_up": "Follow-up needed", "no_answer": "No answer"}


class CallBody(BaseModel):
    outcome: str
    note: str = ""


@router.post("/{cid}/call")
def log_call(cid: str, b: CallBody, db: Session = Depends(get_db), user: User = Depends(require("cases", "create"))):
    c = get_case(db, cid, user)
    if b.outcome not in CALL_OUTCOMES:
        raise HTTPException(422, "Choose a call outcome.")
    db.add(CaseCall(case_id=c.id, outcome=b.outcome, note=b.note.strip(), actor=user.name))
    text = f"Called patient: {CALL_OUTCOMES[b.outcome]}" + (f". {b.note.strip()}" if b.note.strip() else "")
    db.add(CaseEvent(case_id=c.id, kind="call", text=text, actor=user.name))
    audit.log(db, user, "cases", "call", "case", c.id, f"Call logged on {c.number}: {CALL_OUTCOMES[b.outcome]}")
    db.commit()
    return {"ok": True}


@router.post("/{cid}/raise-incident")
def raise_incident(cid: str, db: Session = Depends(get_db), user: User = Depends(require("cases", "create"))):
    """One click from a complaint to an incident: patient, department and text carry over, and both records link to each other."""
    c = get_case(db, cid, user)
    if not can(user, "incidents", "create"):
        raise HTTPException(403, "Your role cannot raise incidents.")
    if c.incident_id:
        raise HTTPException(409, "An incident is already linked to this case.")
    fb = db.get(FeedbackResponse, c.feedback_id) if c.feedback_id else None
    text = ((fb.ai or {}).get("translation_en") or fb.text) if fb and fb.text else c.title
    dept = db.get(Department, c.department_id) if c.department_id else None
    inc = create_incident(db, user, f"Raised from complaint {c.number}. Patient feedback: {text}", c.created_at, department_id=c.department_id,
                          location=dept.name if dept else "", patient_id=c.patient_id, case_id=c.id, title=f"Complaint {c.number}: {c.title}"[:300])
    c.incident_id = inc.id
    db.add(CaseEvent(case_id=c.id, kind="incident", text=f"Incident {inc.number} raised from this case", actor=user.name))
    db.add(IncidentEvent(incident_id=inc.id, kind="linked", text=f"Linked to complaint case {c.number}", actor=user.name))
    audit.log(db, user, "cases", "raise_incident", "case", c.id, f"{c.number} → incident {inc.number}")
    db.commit()
    return {"incident_id": inc.id, "number": inc.number}


@router.post("/{cid}/closing-message")
def closing_message(cid: str, db: Session = Depends(get_db), user: User = Depends(require("cases", "create"))):
    """Optional last step of service recovery: tell the patient the case is closed."""
    c = get_case(db, cid, user)
    if c.status not in ("Resolved", "Closed"):
        raise HTTPException(422, "Resolve or close the case before sending a closing message.")
    if c.closing_message_at:
        raise HTTPException(409, "A closing message was already sent.")
    p = db.get(Patient, c.patient_id)
    if p.mrn == "WALKUP":
        raise HTTPException(422, "This feedback came from a QR code, so there is no patient to message.")
    whatsapp.send_closing_message(db, p, p.language)
    c.closing_message_at = now()
    db.add(CaseEvent(case_id=c.id, kind="note", text="Closing message sent to the patient", actor=user.name))
    audit.log(db, user, "cases", "closing_message", "case", c.id, f"Closing message sent for {c.number}")
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
    if owner and not can(owner, "cases", "create"):
        raise HTTPException(422, "Choose someone whose role can work on cases.")
    for c in cases:
        if owner:
            _assign(db, c, owner, user)
        if b.close:
            c.status, c.resolution, c.closed_at = "Closed", b.resolution, c.closed_at or now()
            db.add(CaseEvent(case_id=c.id, kind="closed", text=f"Closed: {b.resolution}", actor=user.name))
            audit.log(db, user, "cases", "status", "case", c.id, f"{c.number} closed (bulk)")
    db.commit()
    return {"updated": len(cases)}

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import audit
from ..ai.incident import suggest
from ..db import get_db
from ..defaults import FACTOR_GROUPS, HARM_LEVELS, INCIDENT_CATEGORIES, INCIDENT_STATUSES
from ..models import Capa, Case, Department, Incident, IncidentEvent, Patient, User, now
from ..security import can, current_user, dept_scope, require
from ..services import (create_incident, get_setting, incident_due, is_sentinel, notify, users_with_role)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])
CAT = dict(INCIDENT_CATEGORIES)
HARM = dict(HARM_LEVELS)
GROUPS = [k for k, _ in FACTOR_GROUPS]


def visible(stmt, user: User):
    """Approvers and all-department roles see everything; others see their departments and their own reports."""
    if can(user, "incidents", "approve"):
        return stmt
    scope = dept_scope(user)
    return stmt if scope is None else stmt.where(or_(Incident.department_id.in_(scope), Incident.reported_by == user.id))


def get_incident(db: Session, iid: str, user: User) -> Incident:
    i = db.scalar(visible(select(Incident).where(Incident.id == iid), user))
    if not i:
        raise HTTPException(404, "Incident not found")
    return i


def can_work(user: User, i: Incident) -> bool:
    return can(user, "incidents", "approve") or i.investigator_id == user.id


def names(db):
    return {u.id: u.name for u in db.scalars(select(User))}, {d.id: d.name for d in db.scalars(select(Department))}


def row(i: Incident, users: dict, depts: dict):
    overdue = i.status != "Closed" and i.due_at is not None and i.due_at < now()
    return {"id": i.id, "number": i.number, "title": i.title, "category": i.category, "category_label": CAT.get(i.category, i.category),
            "harm": i.harm, "harm_label": HARM.get(i.harm, i.harm), "status": i.status, "department_id": i.department_id,
            "department": depts.get(i.department_id, "—"), "location": i.location, "occurred_at": i.occurred_at, "created_at": i.created_at,
            "due_at": i.due_at, "overdue": overdue, "sentinel": i.sentinel, "escalated_at": i.escalated_at,
            "investigator_id": i.investigator_id, "investigator": users.get(i.investigator_id, "Unassigned"),
            "reporter": "Anonymous" if i.anonymous else users.get(i.reported_by, "—"), "case_id": i.case_id}


def view_or_report(user: User = Depends(current_user)) -> User:
    if not (can(user, "incidents", "view") or can(user, "incidents", "create")):
        raise HTTPException(403, "Your role does not allow access to incidents.")
    return user


@router.get("/meta")
def meta(db: Session = Depends(get_db), user: User = Depends(view_or_report)):
    approver = can(user, "incidents", "approve")
    return {"departments": [{"id": d.id, "name": d.name} for d in db.scalars(select(Department).where(Department.active.is_(True)).order_by(Department.name))],
            "people": [{"id": u.id, "name": u.name} for u in db.scalars(select(User).where(User.active.is_(True)).order_by(User.name))] if approver else [],
            "categories": [{"key": k, "label": v} for k, v in INCIDENT_CATEGORIES], "harms": [{"key": k, "label": v} for k, v in HARM_LEVELS],
            "statuses": INCIDENT_STATUSES, "factor_groups": [{"key": k, "label": v} for k, v in FACTOR_GROUPS]}


@router.get("")
def list_incidents(page: int = 1, size: int = Query(20, le=100), sort: str = "created_at", order: str = "desc", status: str | None = None,
                   harm: str | None = None, category: str | None = None, department_id: str | None = None, sentinel: bool | None = None,
                   overdue: bool | None = None, open: bool | None = None, mine: bool | None = None, q: str | None = None,
                   db: Session = Depends(get_db), user: User = Depends(require("incidents"))):
    stmt = visible(select(Incident), user)
    for col, val in ((Incident.status, status), (Incident.harm, harm), (Incident.category, category), (Incident.department_id, department_id)):
        if val:
            stmt = stmt.where(col == val)
    if sentinel:
        stmt = stmt.where(Incident.sentinel.is_(True))
    if open:
        stmt = stmt.where(Incident.status != "Closed")
    if overdue:
        stmt = stmt.where(Incident.status != "Closed", Incident.due_at < now())
    if mine:
        stmt = stmt.where(or_(Incident.reported_by == user.id, Incident.investigator_id == user.id))
    if q:
        stmt = stmt.where(Incident.title.ilike(f"%{q}%") | Incident.number.ilike(f"%{q}%") | Incident.description.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = getattr(Incident, sort if sort in ("created_at", "occurred_at", "due_at", "harm", "status", "number") else "created_at")
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc()).offset((page - 1) * size).limit(size)
    users, depts = names(db)
    return {"total": total, "items": [row(i, users, depts) for i in db.scalars(stmt)]}


def similar(db: Session, category: str, dept_id: str | None, exclude: str | None = None, with_items: bool = False):
    since = now() - timedelta(days=90)
    stmt = select(Incident).where(Incident.category == category, Incident.occurred_at >= since)
    if dept_id:
        stmt = stmt.where(Incident.department_id == dept_id)
    if exclude:
        stmt = stmt.where(Incident.id != exclude)
    found = db.scalars(stmt.order_by(Incident.occurred_at.desc())).all()
    dept = db.get(Department, dept_id).name if dept_id else "all departments"
    noun = "" if category == "other" else CAT.get(category, category).lower() + " "
    label = f"{len(found)} similar {noun}incident{'s' if len(found) != 1 else ''} in {dept} in the last 90 days" if found else ""
    out = {"count": len(found), "label": label}
    if with_items:
        out["items"] = [{"id": f.id, "number": f.number, "title": f.title, "occurred_at": f.occurred_at, "harm_label": HARM.get(f.harm, f.harm)} for f in found[:5]]
    return out


class SuggestBody(BaseModel):
    text: str = Field(min_length=10, max_length=4000)
    department_id: str | None = None


@router.post("/ai-suggest")
def ai_suggest(b: SuggestBody, db: Session = Depends(get_db), user: User = Depends(require("incidents", "create"))):
    s, status = suggest(b.text)
    return s | {"status": status, "similar": similar(db, s["category"], b.department_id, with_items=can(user, "incidents", "approve"))}


class Report(BaseModel):
    description: str = Field(min_length=10, max_length=4000)
    occurred_at: datetime
    category: str | None = None
    harm: str | None = None
    department_id: str | None = None
    location: str = ""
    immediate_action: str = ""
    anonymous: bool = False
    patient_id: str | None = None


@router.post("")
def report(b: Report, db: Session = Depends(get_db), user: User = Depends(require("incidents", "create"))):
    if b.category and b.category not in CAT or b.harm and b.harm not in HARM:
        raise HTTPException(422, "Unknown category or harm level.")
    if b.occurred_at.astimezone() > datetime.now().astimezone() + timedelta(minutes=5):
        raise HTTPException(422, "The time of the incident cannot be in the future.")
    inc = create_incident(db, user, b.description, b.occurred_at, category=b.category, harm=b.harm, department_id=b.department_id, location=b.location,
                          immediate_action=b.immediate_action, anonymous=b.anonymous, patient_id=b.patient_id)
    db.commit()
    return {"id": inc.id, "number": inc.number, "sentinel": inc.sentinel}


# ---------- CAPA list (before /{iid} so the path is not read as an id)
@router.get("/capas")
def list_capas(overdue: bool | None = None, mine: bool | None = None, status: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("incidents"))):
    stmt = select(Capa, Incident).join(Incident, Incident.id == Capa.incident_id)
    stmt = visible(stmt, user)
    if mine:
        stmt = stmt.where(Capa.owner_id == user.id)
    if status:
        stmt = stmt.where(Capa.status == status)
    if overdue:
        stmt = stmt.where(Capa.status != "Completed", Capa.due_at < now())
    users, _ = names(db)
    return [capa_row(c, users) | {"incident_number": i.number, "incident_title": i.title} for c, i in db.execute(stmt.order_by(Capa.due_at))]


def capa_row(c: Capa, users: dict):
    return {"id": c.id, "incident_id": c.incident_id, "kind": c.kind, "action": c.action, "owner_id": c.owner_id, "owner": users.get(c.owner_id, "Unassigned"),
            "due_at": c.due_at, "status": c.status, "completed_at": c.completed_at, "check_due_at": c.check_due_at, "check_result": c.check_result,
            "check_note": c.check_note, "overdue": c.status != "Completed" and c.due_at < now(),
            "check_overdue": c.status == "Completed" and not c.check_result and c.check_due_at is not None and c.check_due_at < now()}


@router.get("/{iid}")
def detail(iid: str, db: Session = Depends(get_db), user: User = Depends(require("incidents"))):
    i = get_incident(db, iid, user)
    users, depts = names(db)
    events = db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id == i.id).order_by(IncidentEvent.at)).all()
    capas = db.scalars(select(Capa).where(Capa.incident_id == i.id).order_by(Capa.due_at)).all()
    patient = db.get(Patient, i.patient_id) if i.patient_id else None
    masked = get_setting(db, "routing").get("mask_patient_names", False)
    case = db.get(Case, i.case_id) if i.case_id else None
    return row(i, users, depts) | {
        "description": i.description, "immediate_action": i.immediate_action, "anonymous": i.anonymous, "root_cause": i.root_cause,
        "contributing_factors": {g: (i.contributing_factors or {}).get(g, []) for g in GROUPS}, "why_chain": i.why_chain or [],
        "ai": i.ai, "closed_at": i.closed_at, "can_work": can_work(user, i), "can_triage": can(user, "incidents", "approve"),
        "patient": ((" ".join(p[0] + "***" for p in patient.name.split()) if masked else patient.name) + f" · {patient.mrn}") if patient else None,
        "case": {"id": case.id, "number": case.number} if case else None,
        "timeline": [{"id": e.id, "kind": e.kind, "text": e.text, "actor": e.actor, "at": e.at} for e in events],
        "capas": [capa_row(c, users) for c in capas],
        "similar": similar(db, i.category, i.department_id, exclude=i.id, with_items=can(user, "incidents", "approve"))}


def event(db, i: Incident, kind: str, text: str, actor: str, at=None):
    db.add(IncidentEvent(incident_id=i.id, kind=kind, text=text, actor=actor, at=at or now()))


class Triage(BaseModel):
    category: str | None = None
    harm: str | None = None
    investigator_id: str | None = None
    due_at: datetime | None = None
    accept: bool = False


@router.put("/{iid}/triage")
def triage(iid: str, b: Triage, db: Session = Depends(get_db), user: User = Depends(require("incidents", "approve"))):
    i = get_incident(db, iid, user)
    if i.status == "Closed":
        raise HTTPException(409, "This incident is closed. Reopen it first.")
    if b.category and b.category not in CAT or b.harm and b.harm not in HARM:
        raise HTTPException(422, "Unknown category or harm level.")
    before = {"category": i.category, "harm": i.harm, "investigator_id": i.investigator_id, "due_at": i.due_at, "status": i.status}
    parts = []
    if b.category and b.category != i.category:
        parts.append(f"category {CAT[i.category]} → {CAT[b.category]}")
        i.category = b.category
    if b.harm and b.harm != i.harm:
        parts.append(f"harm {HARM[i.harm]} → {HARM[b.harm]}")
        i.harm, i.sentinel = b.harm, is_sentinel(b.harm)
        if not b.due_at:
            i.due_at = incident_due(db, b.harm)
    if b.due_at:
        i.due_at = b.due_at
        parts.append("deadline set")
    if b.investigator_id and b.investigator_id != i.investigator_id:
        inv = db.get(User, b.investigator_id)
        if not inv or not inv.active:
            raise HTTPException(404, "Investigator not found")
        i.investigator_id = inv.id
        parts.append(f"investigator {inv.name}")
        notify(db, inv, "incident", f"Incident {i.number} assigned to you", i.title, f"/quality/incidents/{i.id}")
    if i.investigator_id and i.status in ("Reported", "Triaged"):
        i.status = "Under investigation"
    elif b.accept and i.status == "Reported":
        i.status = "Triaged"
    if b.accept or parts:
        event(db, i, "triaged", ("Triaged: " + "; ".join(parts)) if parts else "Accepted at triage", user.name)
    audit.log(db, user, "incidents", "triage", "incident", i.id, f"{i.number} triaged", before,
              {"category": i.category, "harm": i.harm, "investigator_id": i.investigator_id, "due_at": i.due_at, "status": i.status})
    db.commit()
    return {"ok": True}


class Investigation(BaseModel):
    contributing_factors: dict[str, list[str]] | None = None
    why_chain: list[str] | None = None
    root_cause: str | None = None


@router.put("/{iid}/investigation")
def investigation(iid: str, b: Investigation, db: Session = Depends(get_db), user: User = Depends(require("incidents", "create"))):
    i = get_incident(db, iid, user)
    if not can_work(user, i):
        raise HTTPException(403, "Only the assigned investigator or the Quality team can edit the investigation.")
    if i.status == "Closed":
        raise HTTPException(409, "This incident is closed. Reopen it first.")
    before = {"factors": i.contributing_factors, "why_chain": i.why_chain, "root_cause": i.root_cause}
    if b.contributing_factors is not None:
        if set(b.contributing_factors) - set(GROUPS):
            raise HTTPException(422, "Unknown contributing factor group.")
        i.contributing_factors = {g: [t.strip() for t in v if t.strip()] for g, v in b.contributing_factors.items()}
    if b.why_chain is not None:
        i.why_chain = [w.strip() for w in b.why_chain if w.strip()][:5]
    if b.root_cause is not None:
        i.root_cause = b.root_cause.strip()
    event(db, i, "note", "Investigation updated", user.name)
    audit.log(db, user, "incidents", "investigation", "incident", i.id, f"Investigation updated on {i.number}", before,
              {"factors": i.contributing_factors, "why_chain": i.why_chain, "root_cause": i.root_cause})
    db.commit()
    return {"ok": True}


class Fact(BaseModel):
    at: datetime
    text: str = Field(min_length=3, max_length=1000)


@router.post("/{iid}/facts")
def add_fact(iid: str, b: Fact, db: Session = Depends(get_db), user: User = Depends(require("incidents", "create"))):
    i = get_incident(db, iid, user)
    if not can_work(user, i):
        raise HTTPException(403, "Only the assigned investigator or the Quality team can add to the timeline.")
    event(db, i, "fact", b.text.strip(), user.name, at=b.at)
    audit.log(db, user, "incidents", "timeline", "incident", i.id, f"Timeline entry added to {i.number}")
    db.commit()
    return {"ok": True}


class CapaBody(BaseModel):
    kind: str = "corrective"
    action: str = Field(min_length=5, max_length=2000)
    owner_id: str | None = None
    due_at: datetime
    check_due_at: datetime | None = None


@router.post("/{iid}/capas")
def add_capa(iid: str, b: CapaBody, db: Session = Depends(get_db), user: User = Depends(require("incidents", "create"))):
    i = get_incident(db, iid, user)
    if not can_work(user, i):
        raise HTTPException(403, "Only the assigned investigator or the Quality team can add actions.")
    if b.kind not in ("corrective", "preventive"):
        raise HTTPException(422, "Action type must be corrective or preventive.")
    owner = db.get(User, b.owner_id) if b.owner_id else None
    c = Capa(incident_id=i.id, kind=b.kind, action=b.action.strip(), owner_id=owner.id if owner else None, due_at=b.due_at, check_due_at=b.check_due_at)
    db.add(c)
    db.flush()
    if i.status in ("Reported", "Triaged", "Under investigation"):
        i.status = "Actions open"
    event(db, i, "capa", f"{b.kind.capitalize()} action added: {c.action[:200]}", user.name)
    if owner:
        notify(db, owner, "capa", f"Action assigned on {i.number}", c.action[:300], f"/quality/incidents/{i.id}")
    audit.log(db, user, "incidents", "capa_add", "capa", c.id, f"Action added to {i.number}", None, {"kind": b.kind, "owner_id": c.owner_id, "due_at": b.due_at.isoformat()})
    db.commit()
    return {"id": c.id}


class CapaEdit(BaseModel):
    action: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None
    status: str | None = None
    check_due_at: datetime | None = None
    check_result: str | None = None
    check_note: str | None = None


@router.put("/capas/{cid}")
def edit_capa(cid: str, b: CapaEdit, db: Session = Depends(get_db), user: User = Depends(require("incidents", "create"))):
    c = db.get(Capa, cid)
    i = get_incident(db, c.incident_id, user) if c else None
    if not c:
        raise HTTPException(404, "Action not found")
    if not (can_work(user, i) or c.owner_id == user.id):
        raise HTTPException(403, "Only the action owner, the investigator or the Quality team can update this action.")
    if b.status and b.status not in ("Open", "In progress", "Completed"):
        raise HTTPException(422, "Status must be Open, In progress or Completed.")
    if b.check_result and b.check_result not in ("effective", "not_effective"):
        raise HTTPException(422, "Effectiveness must be effective or not_effective.")
    before = {"status": c.status, "owner_id": c.owner_id, "due_at": c.due_at, "check_result": c.check_result}
    for f in ("action", "due_at", "check_due_at", "check_note"):
        v = getattr(b, f)
        if v is not None:
            setattr(c, f, v.strip() if isinstance(v, str) else v)
    if b.owner_id:
        c.owner_id = b.owner_id
    note = []
    if b.status and b.status != c.status:
        c.status = b.status
        note.append(f"status {b.status}")
        if b.status == "Completed":
            c.completed_at = now()
            c.check_due_at = c.check_due_at or now() + timedelta(days=60)
        else:
            c.completed_at = None
    if b.check_result:
        if c.status != "Completed":
            raise HTTPException(422, "Complete the action before recording an effectiveness check.")
        c.check_result = b.check_result
        note.append("effectiveness check: " + ("effective" if b.check_result == "effective" else "not effective"))
    if note:
        event(db, i, "capa", f"Action updated ({', '.join(note)}): {c.action[:120]}", user.name)
    audit.log(db, user, "incidents", "capa_update", "capa", c.id, f"Action updated on {i.number}", before,
              {"status": c.status, "owner_id": c.owner_id, "due_at": c.due_at, "check_result": c.check_result})
    db.commit()
    return {"ok": True}


@router.post("/{iid}/escalate")
def escalate(iid: str, db: Session = Depends(get_db), user: User = Depends(require("incidents", "approve"))):
    i = get_incident(db, iid, user)
    if i.escalated_at:
        raise HTTPException(409, "Already escalated to management.")
    i.escalated_at = now()
    event(db, i, "escalated", "Escalated to management", user.name)
    for role in ("management_viewer", "admin"):
        for u in users_with_role(db, role):
            notify(db, u, "incident", f"Escalated to management: {i.number}", i.title, f"/quality/incidents/{i.id}")
    audit.log(db, user, "incidents", "escalate", "incident", i.id, f"{i.number} escalated to management")
    db.commit()
    return {"ok": True}


class StatusBody(BaseModel):
    status: str


@router.post("/{iid}/status")
def set_status(iid: str, b: StatusBody, db: Session = Depends(get_db), user: User = Depends(require("incidents", "approve"))):
    i = get_incident(db, iid, user)
    if b.status not in ("Closed", "Under investigation"):
        raise HTTPException(422, "Status can only be changed to Closed or reopened to Under investigation.")
    before = {"status": i.status}
    if b.status == "Closed":
        if not i.root_cause:
            raise HTTPException(422, "Record a root cause statement before closing.")
        n_capa = db.scalar(select(func.count()).select_from(Capa).where(Capa.incident_id == i.id))
        if i.harm in ("moderate", "severe", "death") and not n_capa:
            raise HTTPException(422, "Add at least one corrective or preventive action before closing a moderate or serious incident.")
        if i.sentinel and not i.escalated_at:
            raise HTTPException(422, "Escalate this serious event to management before closing.")
        i.status, i.closed_at = "Closed", now()
        event(db, i, "closed", "Incident closed", user.name)
    else:
        i.status, i.closed_at, i.breach_notified = "Under investigation", None, False
        event(db, i, "status", "Incident reopened", user.name)
    audit.log(db, user, "incidents", "status", "incident", i.id, f"{i.number} → {i.status}", before, {"status": i.status})
    db.commit()
    return {"ok": True}

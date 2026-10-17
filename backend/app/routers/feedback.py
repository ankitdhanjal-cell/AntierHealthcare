from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Text, func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Case, Department, FeedbackRequest, FeedbackResponse, Patient, User
from ..security import dept_scope, require
from ..services import get_setting, open_case

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


def mask(name: str, on: bool):
    return " ".join(p[0] + "***" for p in name.split()) if on else name


def row(f: FeedbackResponse, db: Session, masked=False, depts=None):
    depts = depts or {d.id: d.name for d in db.scalars(select(Department))}
    ai = f.ai or {}
    return {"id": f.id, "created_at": f.created_at, "patient": mask(f.patient.name, masked), "rating": f.rating,
            "department_id": f.department_id, "department": depts.get(f.department_id, "—"), "language": f.language,
            "sentiment": f.sentiment, "themes": f.themes, "urgency": f.urgency, "text": f.text,
            "summary": ai.get("summary", ""), "reviewed": f.reviewed, "ai_status": f.ai_status, "case_id": f.case_id}


def scoped(q, user: User):
    scope = dept_scope(user)
    if scope is not None:
        q = q.where(FeedbackResponse.department_id.in_(scope))
    return q


@router.get("")
def inbox(page: int = 1, size: int = Query(20, le=100), sort: str = "created_at", order: str = "desc",
          department_id: str | None = None, rating: int | None = None, sentiment: str | None = None,
          theme: str | None = None, language: str | None = None, reviewed: bool | None = None,
          q: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("feedback"))):
    stmt = scoped(select(FeedbackResponse), user)
    if department_id:
        stmt = stmt.where(FeedbackResponse.department_id == department_id)
    if rating:
        stmt = stmt.where(FeedbackResponse.rating == rating)
    if sentiment:
        stmt = stmt.where(FeedbackResponse.sentiment == sentiment)
    if language:
        stmt = stmt.where(FeedbackResponse.language == language)
    if reviewed is not None:
        stmt = stmt.where(FeedbackResponse.reviewed == reviewed)
    if theme:
        stmt = stmt.where(FeedbackResponse.themes.cast(Text).like(f'%"{theme}"%'))
    if q:
        stmt = stmt.where(FeedbackResponse.text.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = getattr(FeedbackResponse, sort if sort in ("created_at", "rating", "sentiment", "urgency") else "created_at")
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc()).offset((page - 1) * size).limit(size)
    masked = get_setting(db, "routing").get("mask_patient_names", False)
    depts = {d.id: d.name for d in db.scalars(select(Department))}
    return {"total": total, "items": [row(f, db, masked, depts) for f in db.scalars(stmt)]}


@router.get("/review-requests")
def review_requests(db: Session = Depends(get_db), user: User = Depends(require("feedback"))):
    rows = db.execute(select(FeedbackRequest, Patient.name).join(Patient, Patient.id == FeedbackRequest.patient_id)
                      .where(FeedbackRequest.google_invited.is_(True)).order_by(FeedbackRequest.created_at.desc()).limit(200))
    return [{"id": r.id, "patient": name, "invited_at": r.sent_at or r.created_at, "clicked": r.google_clicked} for r, name in rows]


@router.get("/{fid}")
def detail(fid: str, db: Session = Depends(get_db), user: User = Depends(require("feedback"))):
    f = db.get(FeedbackResponse, fid)
    scope = dept_scope(user)
    if not f or (scope is not None and f.department_id not in scope):
        raise HTTPException(404, "Feedback not found")
    masked = get_setting(db, "routing").get("mask_patient_names", False)
    case = db.get(Case, f.case_id) if f.case_id else None
    return row(f, db, masked) | {"answers": f.answers, "ai": f.ai, "accepted": f.accepted,
                                  "case": {"id": case.id, "number": case.number, "status": case.status} if case else None}


class Tags(BaseModel):
    sentiment: str
    themes: list[str]
    urgency: str
    suggested_owner: str | None = None


@router.put("/{fid}/tags")
def accept_tags(fid: str, b: Tags, db: Session = Depends(get_db), user: User = Depends(require("feedback", "create"))):
    f = db.get(FeedbackResponse, fid)
    if not f:
        raise HTTPException(404)
    before = {"sentiment": f.sentiment, "themes": f.themes, "urgency": f.urgency}
    f.sentiment, f.themes, f.urgency = b.sentiment, b.themes, b.urgency
    f.accepted = b.model_dump()
    f.reviewed = True
    audit.log(db, user, "feedback", "accept_ai", "feedback", f.id, "AI tags accepted/edited",
              {"ai_suggested": f.ai, **before}, b.model_dump())
    db.commit()
    return {"ok": True}


@router.post("/{fid}/open-case")
def open_case_manual(fid: str, db: Session = Depends(get_db), user: User = Depends(require("cases", "create"))):
    f = db.get(FeedbackResponse, fid)
    if not f:
        raise HTTPException(404)
    if f.case_id:
        raise HTTPException(409, "A case already exists for this feedback.")
    depts = {d.name: d.id for d in db.scalars(select(Department))}
    dept = depts.get((f.ai or {}).get("suggested_owner")) or f.department_id
    c = open_case(db, f, (f.ai or {}).get("summary") or "Patient feedback", f.urgency, dept, user)
    db.commit()
    return {"case_id": c.id}


class Bulk(BaseModel):
    ids: list[str]


@router.post("/bulk-review")
def bulk_review(b: Bulk, db: Session = Depends(get_db), user: User = Depends(require("feedback", "create"))):
    for f in db.scalars(select(FeedbackResponse).where(FeedbackResponse.id.in_(b.ids))):
        f.reviewed = True
    audit.log(db, user, "feedback", "bulk_review", "feedback", "", f"{len(b.ids)} responses marked reviewed")
    db.commit()
    return {"ok": True}

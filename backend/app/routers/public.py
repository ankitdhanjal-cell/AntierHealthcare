from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..ai.feedback import analyse
from ..db import get_db
from ..models import Department, FeedbackRequest, FeedbackResponse, Patient
from ..services import branding, get_setting, open_case

router = APIRouter(prefix="/api/public", tags=["public"])


def _req(db, token):
    r = db.scalar(select(FeedbackRequest).where(FeedbackRequest.token == token))
    if not r:
        raise HTTPException(404, "This feedback link is not valid.")
    return r


@router.get("/feedback/{token}")
def form(token: str, db: Session = Depends(get_db)):
    r = _req(db, token)
    p = db.get(Patient, r.patient_id)
    qs = [q for q in get_setting(db, "questions") if q.get("active", True)][:5]
    return {"branding": branding(db), "language": r.language, "patient_first_name": p.name.split()[0], "answered": r.status == "answered",
            "questions": [{"key": q["key"], "label": q["ar" if r.language == "ar" else "en"]} for q in qs]}


class Submit(BaseModel):
    rating: int = Field(ge=1, le=5)
    answers: dict[str, int] = {}
    text: str = Field("", max_length=3000)
    language: str | None = None


@router.post("/feedback/{token}")
def submit(token: str, b: Submit, db: Session = Depends(get_db)):
    r = _req(db, token)
    if r.status == "answered":
        raise HTTPException(409, "Thank you, your feedback was already received.")
    p = db.get(Patient, r.patient_id)
    themes = get_setting(db, "themes")
    depts = {d.name: d.id for d in db.scalars(select(Department))}
    ai, status = analyse(b.rating, b.answers, b.text, themes, list(depts))
    fb = FeedbackResponse(request_id=r.id, patient_id=p.id, department_id=r.department_id, rating=b.rating, answers=b.answers,
                          text=b.text, language=b.language or r.language, ai=ai, ai_status=status,
                          sentiment=ai["sentiment"], themes=ai["themes"], urgency=ai["urgency"])
    db.add(fb)
    db.flush()
    r.status = "answered"
    rules = get_setting(db, "routing")
    google = b.rating >= rules["min_rating"] and ai["sentiment"] == rules["required_sentiment"] and status == "ok"
    case = None
    if not google:
        title = ai["summary"] if status == "ok" else f"Feedback rated {b.rating}/5 needs review"
        dept = depts.get(ai["suggested_owner"]) or r.department_id
        case = open_case(db, fb, title, ai["urgency"], dept)
    else:
        r.google_invited = True
    audit.log(db, None, "feedback", "create", "feedback", fb.id, f"Feedback received ({b.rating}/5) from {p.name}", None,
              {"ai_suggested": ai, "ai_status": status})
    db.commit()
    return {"google": google, "review_url": rules["google_review_url"] if google else None, "case_opened": bool(case),
            "request_id": r.id}


@router.post("/feedback/{token}/google-click")
def google_click(token: str, db: Session = Depends(get_db)):
    r = _req(db, token)
    r.google_clicked = True
    db.commit()
    return {"ok": True}

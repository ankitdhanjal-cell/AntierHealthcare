from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..ai.feedback import analyse
from ..db import get_db
from ..config import settings as cfg
from ..connectors.sandbox import feedback_message, sms_message
from ..models import Department, FeedbackChannel, FeedbackRequest, FeedbackResponse, Patient
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
    walkup = p.mrn == "WALKUP"
    return {"branding": branding(db), "language": r.language, "patient_first_name": "" if walkup else p.name.split()[0], "answered": r.status == "answered",
            "questions": [{"key": q["key"], "label": q["ar" if r.language == "ar" else "en"]} for q in qs]}


class Submit(BaseModel):
    rating: int = Field(ge=1, le=5)
    nps: int | None = Field(default=None, ge=0, le=10)
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
                          sentiment=ai["sentiment"], themes=ai["themes"], urgency=ai["urgency"], nps=b.nps, attending=p.attending,
                          staff_mentions=ai.get("staff_mentions", []), channel_id=r.channel_id)
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


# ---------- walk-up feedback from a printed QR code, and previews for staff
def _walkup_patient(db, ch: FeedbackChannel, language: str) -> Patient:
    p = db.scalar(select(Patient).where(Patient.mrn == "WALKUP", Patient.department_id == ch.department_id, Patient.name == f"Walk-up respondent ({ch.name})"))
    if not p:
        p = Patient(mrn="WALKUP", name=f"Walk-up respondent ({ch.name})", language=language, department_id=ch.department_id, ward=ch.name)
        db.add(p)
        db.flush()
    return p


class Start(BaseModel):
    language: str = "en"


@router.get("/channel/{token}")
def channel_info(token: str, db: Session = Depends(get_db)):
    ch = db.scalar(select(FeedbackChannel).where(FeedbackChannel.token == token, FeedbackChannel.active.is_(True)))
    if not ch:
        raise HTTPException(404, "This QR code is not active.")
    return {"name": ch.name, "branding": branding(db)}


@router.post("/channel/{token}/start")
def channel_start(token: str, b: Start, db: Session = Depends(get_db)):
    """Scanning a ward or clinic QR code opens the same form as a discharge request, without a patient record."""
    ch = db.scalar(select(FeedbackChannel).where(FeedbackChannel.token == token, FeedbackChannel.active.is_(True)))
    if not ch:
        raise HTTPException(404, "This QR code is not active.")
    lang = "ar" if b.language == "ar" else "en"
    p = _walkup_patient(db, ch, lang)
    r = FeedbackRequest(patient_id=p.id, department_id=ch.department_id, language=lang, status="sent", channel="qr", channel_id=ch.id, sent_at=None)
    db.add(r)
    db.commit()
    return {"token": r.token}


@router.get("/preview/{language}")
def preview(language: str, db: Session = Depends(get_db)):
    """What a patient sees: the message and the form, with sample names. Nothing is stored."""
    lang = "ar" if language == "ar" else "en"
    b = branding(db)
    qs = [q for q in get_setting(db, "questions") if q.get("active", True)][:5]
    link = f"{cfg.public_web_url}/f/sample"
    return {"language": lang, "branding": b, "whatsapp": feedback_message(b, "Mariam" if lang == "en" else "مريم", lang), "sms": sms_message(b, lang, link), "link": link,
            "patient_first_name": "Mariam" if lang == "en" else "مريم", "answered": False,
            "questions": [{"key": q["key"], "label": q["ar" if lang == "ar" else "en"]} for q in qs]}

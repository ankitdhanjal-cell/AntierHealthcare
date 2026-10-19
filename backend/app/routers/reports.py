from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..committee_pack import build_pdf, collect, fmt_value, period_label, valid
from ..db import get_db
from ..indicators_calc import completed_periods
from ..models import CommitteeReport, User, now
from ..security import require
from ..services import get_setting

router = APIRouter(prefix="/api/reports", tags=["reports"])


def check(period: str):
    if not valid(period):
        raise HTTPException(422, "Month must be written as YYYY-MM.")
    if period > completed_periods(1)[-1]:
        raise HTTPException(422, "The committee pack covers completed months only.")


def survey_info(db):
    s = get_setting(db, "accreditation")
    if not s.get("survey_date"):
        return None
    d = date.fromisoformat(s["survey_date"])
    return {"days_left": (d - date.today()).days, "date": d.strftime("%d %b %Y")}


@router.get("/committee")
def periods(db: Session = Depends(get_db), user: User = Depends(require("reports"))):
    notes = {r.period: r for r in db.scalars(select(CommitteeReport))}
    return [{"period": p, "label": period_label(p), "has_note": bool(notes.get(p) and notes[p].cover_note.strip()),
             "generated_at": notes[p].generated_at if p in notes else None, "generated_by": notes[p].generated_by if p in notes else ""} for p in reversed(completed_periods(12))]


@router.get("/committee/{period}")
def preview(period: str, db: Session = Depends(get_db), user: User = Depends(require("reports"))):
    check(period)
    d = collect(db, period)
    note = db.scalar(select(CommitteeReport).where(CommitteeReport.period == period))
    return {"period": period, "label": period_label(period), "cover_note": note.cover_note if note else "", "readiness": d["readiness"], "survey": survey_info(db),
            "kpis": [{"name": k["ind"].name, "value": fmt_value(k["ind"], k["value"]), "target": fmt_value(k["ind"], k["ind"].target), "rag": k["rag"]} for k in d["kpis"]],
            "incident_total": d["incident_total"], "serious": len(d["serious"]), "overdue_actions": len(d["overdue_actions"]), "overdue_audits": d["overdue_audits"],
            "themes": d["themes"], "audits": d["audits"], "charts": len(d["charts"])}


class Note(BaseModel):
    cover_note: str


@router.put("/committee/{period}/note")
def save_note(period: str, b: Note, db: Session = Depends(get_db), user: User = Depends(require("reports", "create"))):
    check(period)
    if len(b.cover_note) > 4000:
        raise HTTPException(422, "The cover note can be up to 4,000 characters.")
    r = db.scalar(select(CommitteeReport).where(CommitteeReport.period == period)) or CommitteeReport(period=period)
    before = r.cover_note
    r.cover_note = b.cover_note.strip()
    db.add(r)
    audit.log(db, user, "reports", "note", "report", period, f"Committee pack cover note saved for {period_label(period)}", {"cover_note": before}, {"cover_note": r.cover_note})
    db.commit()
    return {"ok": True}


@router.get("/committee/{period}/pdf")
def pdf(period: str, db: Session = Depends(get_db), user: User = Depends(require("reports"))):
    check(period)
    d = collect(db, period)
    r = db.scalar(select(CommitteeReport).where(CommitteeReport.period == period)) or CommitteeReport(period=period)
    data = build_pdf(d, r.cover_note or "", user.name, survey_info(db))
    r.generated_at, r.generated_by = now(), user.name
    db.add(r)
    audit.log(db, user, "reports", "export", "report", period, f"Committee pack exported for {period_label(period)}")
    db.commit()
    return Response(data, media_type="application/pdf", headers={"content-disposition": f'attachment; filename="committee-pack-{period}.pdf"'})

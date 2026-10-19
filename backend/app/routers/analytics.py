from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Department, FeedbackRequest, FeedbackResponse, User
from ..security import dept_scope, require
from ..services import day_bounds, hospital_tz

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def since_date(months: int) -> str:
    y, m = date.today().year, date.today().month - (months - 1)
    while m < 1:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}-01"


def nps_of(scores: list[int]) -> dict:
    n = len(scores)
    if not n:
        return {"nps": None, "promoters": 0, "passives": 0, "detractors": 0, "count": 0}
    pro, det = sum(s >= 9 for s in scores), sum(s <= 6 for s in scores)
    return {"nps": round(100 * (pro - det) / n), "promoters": pro, "passives": n - pro - det, "detractors": det, "count": n}


@router.get("/nps")
def nps(months: int = Query(6, ge=1, le=24), min_responses: int = Query(5, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(require("feedback"))):
    """Net Promoter Score: percent promoters (9-10) minus percent detractors (0-6), by department and by attending doctor."""
    since = since_date(months)
    start, _ = day_bounds(db, since, None)
    stmt = select(FeedbackResponse).where(FeedbackResponse.nps.isnot(None), FeedbackResponse.created_at >= start)
    scope = dept_scope(user)
    if scope is not None:
        stmt = stmt.where(FeedbackResponse.department_id.in_(scope))
    rows = db.scalars(stmt).all()
    depts = {d.id: d.name for d in db.scalars(select(Department))}
    tz = hospital_tz(db)
    by_dept, by_doc, by_month = defaultdict(list), defaultdict(list), defaultdict(list)
    for f in rows:
        by_dept[f.department_id].append(f.nps)
        if f.attending:
            by_doc[f.attending].append(f.nps)
        by_month[f.created_at.astimezone(tz).strftime("%Y-%m")].append(f.nps)
    pack = lambda g, key: sorted([{key: k} | nps_of(v) for k, v in g.items() if len(v) >= min_responses], key=lambda x: -(x["nps"] if x["nps"] is not None else -999))
    dept_rows = pack({depts.get(k, "—"): v for k, v in by_dept.items()}, "department")
    return {"since": since, "overall": nps_of([f.nps for f in rows]), "by_department": dept_rows, "by_doctor": pack(by_doc, "doctor"),
            "trend": [{"month": m} | nps_of(v) for m, v in sorted(by_month.items())], "min_responses": min_responses}


@router.get("/funnel")
def funnel(months: int = Query(6, ge=1, le=24), db: Session = Depends(get_db), user: User = Depends(require("feedback"))):
    """Review funnel: requests sent, responses, satisfied patients, invited to Google, clicked through."""
    since = since_date(months)
    start, _ = day_bounds(db, since, None)
    sent = db.scalar(select(func.count()).select_from(FeedbackRequest).where(FeedbackRequest.sent_at.isnot(None), FeedbackRequest.sent_at >= start))
    resp = select(FeedbackResponse).where(FeedbackResponse.created_at >= start)
    n_resp = db.scalar(select(func.count()).select_from(resp.subquery()))
    satisfied = db.scalar(select(func.count()).select_from(resp.where(FeedbackResponse.rating >= 4, FeedbackResponse.sentiment == "positive").subquery()))
    ids = select(FeedbackResponse.request_id).where(FeedbackResponse.created_at >= start)
    invited = db.scalar(select(func.count()).select_from(FeedbackRequest).where(FeedbackRequest.google_invited.is_(True), FeedbackRequest.id.in_(ids)))
    clicked = db.scalar(select(func.count()).select_from(FeedbackRequest).where(FeedbackRequest.google_clicked.is_(True), FeedbackRequest.id.in_(ids)))
    steps = [("Requests sent", sent, "/feedback/reviews"), ("Responses", n_resp, f"/feedback?date_from={since}"), ("Satisfied (4-5 stars, positive)", satisfied, f"/feedback?sentiment=positive&date_from={since}"),
             ("Invited to Google", invited, "/feedback/reviews"), ("Clicked through", clicked, "/feedback/reviews")]
    out, prev = [], None
    for label, v, href in steps:
        out.append({"label": label, "value": v, "pct_of_previous": round(100 * v / prev, 1) if prev else None, "pct_of_sent": round(100 * v / sent, 1) if sent else None, "href": href})
        prev = v
    return {"since": since, "steps": out}

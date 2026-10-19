import re
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..defaults import INCIDENT_CATEGORIES
from ..indicators_calc import completed_periods, rag, run_chart, series, status_label
from ..models import FeedbackResponse, Incident, Indicator, IndicatorValue, User, now
from ..security import require
from ..services import day_bounds, hospital_tz

router = APIRouter(prefix="/api/indicators", tags=["indicators"])
DRILL = {"satisfaction": "/feedback", "closure_time": "/cases?closed=true", "sla_closure": "/cases?closed=true", "hand_hygiene": "/quality/audits"}


def people(db):
    return {u.id: u.name for u in db.scalars(select(User))}


def out(ind: Indicator, users: dict, pts: list[dict], with_series: bool = False):
    chart = run_chart(pts)
    latest = pts[-1] if pts else None
    d = {"id": ind.id, "key": ind.key, "name": ind.name, "definition": ind.definition, "numerator": ind.numerator, "denominator": ind.denominator,
         "multiplier": ind.multiplier, "unit": ind.unit, "target": ind.target, "amber": ind.amber, "direction": ind.direction, "frequency": ind.frequency,
         "source": ind.source, "auto": bool(ind.auto), "owner_id": ind.owner_id, "owner": users.get(ind.owner_id, "Unassigned"),
         "latest": latest, "previous": pts[-2] if len(pts) > 1 else None, "rag": rag(ind, latest["value"] if latest else None),
         "median": chart["median"], "shift": chart["shift"], "shift_label": status_label(ind, chart["shift"]), "drill": DRILL.get(ind.auto),
         "spark": [p["value"] for p in pts[-12:]]}
    if with_series:
        d["series"] = pts
    return d


@router.get("")
def dictionary(months: int = Query(12, ge=3, le=24), db: Session = Depends(get_db), user: User = Depends(require("indicators"))):
    periods, users = completed_periods(months), people(db)
    return [out(i, users, series(db, i, periods)) for i in db.scalars(select(Indicator).order_by(Indicator.position))]


class IndicatorBody(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{3,40}$")
    name: str = Field(min_length=3, max_length=200)
    definition: str = Field(min_length=5)
    numerator: str = Field(min_length=3)
    denominator: str = Field(min_length=3)
    multiplier: float = 1
    unit: str = ""
    target: float
    amber: float | None = None
    direction: str = "higher"
    frequency: str = "Monthly"
    source: str = ""
    owner_id: str | None = None


@router.post("")
def create(b: IndicatorBody, db: Session = Depends(get_db), user: User = Depends(require("indicators", "admin"))):
    if b.direction not in ("higher", "lower"):
        raise HTTPException(422, "Direction must be higher or lower.")
    if db.scalar(select(Indicator).where(Indicator.key == b.key)):
        raise HTTPException(409, "An indicator with this key already exists.")
    pos = len(db.scalars(select(Indicator.id)).all())
    ind = Indicator(**b.model_dump(), position=pos)
    db.add(ind)
    db.flush()
    audit.log(db, user, "indicators", "create", "indicator", ind.id, f"Indicator created: {ind.name}")
    db.commit()
    return {"id": ind.id}


# registered before /{iid} so these paths are not read as an id
@router.get("/entry")
def entry(period: str, db: Session = Depends(get_db), user: User = Depends(require("indicators", "create"))):
    _valid(period)
    users = people(db)
    vals = {v.indicator_id: v for v in db.scalars(select(IndicatorValue).where(IndicatorValue.period == period))}
    rows = []
    for i in db.scalars(select(Indicator).where(Indicator.auto == "").order_by(Indicator.position)):
        v = vals.get(i.id)
        rows.append({"id": i.id, "name": i.name, "unit": i.unit, "numerator_label": i.numerator, "denominator_label": i.denominator, "multiplier": i.multiplier,
                     "target": i.target, "owner": users.get(i.owner_id, "Unassigned"), "numerator": v.numerator if v else None, "denominator": v.denominator if v else None,
                     "note": v.note if v else "", "value": round(v.numerator / v.denominator * i.multiplier, 2) if v and v.denominator else None})
    return rows


def _valid(period: str):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise HTTPException(422, "Month must be written as YYYY-MM.")


@router.get("/pareto")
def pareto(source: str = "themes", months: int = Query(6, ge=1, le=24), db: Session = Depends(get_db), user: User = Depends(require("indicators"))):
    """The vital few: complaint themes or incident categories, largest first, with the cumulative share."""
    since_s = (datetime.now(hospital_tz(db)) - timedelta(days=30 * months)).date().isoformat()
    start, _ = day_bounds(db, since_s, None)
    if source == "themes":
        c = Counter(t for f in db.scalars(select(FeedbackResponse).where(FeedbackResponse.created_at >= start, FeedbackResponse.sentiment != "positive")) for t in f.themes)
        items = [{"label": k, "count": v, "href": f"/feedback?theme={k}&not_positive=true&date_from={since_s}"} for k, v in c.most_common()]
        title = "Complaint themes"
    elif source == "incident_categories":
        labels = dict(INCIDENT_CATEGORIES)
        c = Counter(i.category for i in db.scalars(select(Incident).where(Incident.occurred_at >= start)))
        items = [{"label": labels.get(k, k), "count": v, "href": f"/quality/incidents?category={k}"} for k, v in c.most_common()]
        title = "Incident categories"
    else:
        raise HTTPException(422, "Source must be themes or incident_categories.")
    total, run = sum(i["count"] for i in items) or 1, 0
    for i in items:
        run += i["count"]
        i["pct"], i["cumulative"] = round(100 * i["count"] / total, 1), round(100 * run / total, 1)
    vital = [i["label"] for i in items if i["cumulative"] - i["pct"] < 80]
    return {"title": title, "since": since_s, "total": total, "items": items, "vital_few": vital}


@router.get("/{iid}")
def detail(iid: str, months: int = Query(12, ge=3, le=24), db: Session = Depends(get_db), user: User = Depends(require("indicators"))):
    ind = db.get(Indicator, iid)
    if not ind:
        raise HTTPException(404, "Indicator not found")
    return out(ind, people(db), series(db, ind, completed_periods(months)), with_series=True)


class IndicatorEdit(BaseModel):
    name: str | None = None
    definition: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    unit: str | None = None
    target: float | None = None
    amber: float | None = None
    frequency: str | None = None
    source: str | None = None
    owner_id: str | None = None


@router.put("/{iid}")
def edit(iid: str, b: IndicatorEdit, db: Session = Depends(get_db), user: User = Depends(require("indicators", "admin"))):
    ind = db.get(Indicator, iid)
    if not ind:
        raise HTTPException(404, "Indicator not found")
    before = {k: getattr(ind, k) for k in b.model_fields_set}
    for k in b.model_fields_set:
        setattr(ind, k, getattr(b, k))
    audit.log(db, user, "indicators", "edit", "indicator", ind.id, f"Indicator updated: {ind.name}", before, {k: getattr(ind, k) for k in b.model_fields_set})
    db.commit()
    return {"ok": True}


class ValueBody(BaseModel):
    period: str
    numerator: float = Field(ge=0)
    denominator: float = Field(gt=0)
    note: str = ""


@router.put("/{iid}/values")
def enter_value(iid: str, b: ValueBody, db: Session = Depends(get_db), user: User = Depends(require("indicators", "create"))):
    ind = db.get(Indicator, iid)
    if not ind:
        raise HTTPException(404, "Indicator not found")
    if ind.auto:
        raise HTTPException(422, "This indicator is calculated from records and cannot be entered by hand.")
    _valid(b.period)
    if b.period > now().astimezone(hospital_tz(db)).strftime("%Y-%m"):
        raise HTTPException(422, "You cannot enter a value for a future month.")
    if ind.multiplier == 100 and b.numerator > b.denominator:
        raise HTTPException(422, "For a percentage the numerator cannot be larger than the denominator.")
    v = db.scalar(select(IndicatorValue).where(IndicatorValue.indicator_id == iid, IndicatorValue.period == b.period))
    before = {"numerator": v.numerator, "denominator": v.denominator} if v else None
    if not v:
        v = IndicatorValue(indicator_id=iid, period=b.period, numerator=b.numerator, denominator=b.denominator)
        db.add(v)
    v.numerator, v.denominator, v.note, v.entered_by, v.entered_at = b.numerator, b.denominator, b.note.strip(), user.name, now()
    audit.log(db, user, "indicators", "value", "indicator", ind.id, f"{ind.name} {b.period}: {round(b.numerator / b.denominator * ind.multiplier, 2)} {ind.unit}", before,
              {"numerator": b.numerator, "denominator": b.denominator})
    db.commit()
    return {"value": round(b.numerator / b.denominator * ind.multiplier, 2)}

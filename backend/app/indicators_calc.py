"""Quality indicator values: calculated from records for automatic indicators, entered monthly for the rest."""
from datetime import date
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditRun, AuditTemplate, Case, FeedbackResponse, Indicator, IndicatorValue
from .services import hospital_tz


def last_periods(n: int) -> list[str]:
    y, m, out = date.today().year, date.today().month, []
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def completed_periods(n: int) -> list[str]:
    """The last n full months; the current month is still in progress, so run charts leave it out."""
    return last_periods(n + 1)[:-1]


def _auto_rows(db: Session, key: str, periods: list[str]) -> dict[str, tuple[float, float]]:
    """period -> (numerator, denominator)"""
    tz = hospital_tz(db)
    ym = lambda d: d.astimezone(tz).strftime("%Y-%m")
    acc: dict[str, list[float]] = {p: [0.0, 0.0] for p in periods}
    if key == "satisfaction":
        for rating, at in db.execute(select(FeedbackResponse.rating, FeedbackResponse.created_at)):
            if ym(at) in acc:
                acc[ym(at)][0] += rating
                acc[ym(at)][1] += 1
    elif key in ("closure_time", "sla_closure"):
        for c in db.scalars(select(Case).where(Case.closed_at.isnot(None))):
            p = ym(c.closed_at)
            if p in acc:
                acc[p][1] += 1
                acc[p][0] += (c.closed_at - c.created_at).total_seconds() / 3600 if key == "closure_time" else int(c.closed_at <= c.due_at)
    elif key == "hand_hygiene":
        ids = {t.id for t in db.scalars(select(AuditTemplate)) if t.name.lower().startswith("hand hygiene")}
        for r in db.scalars(select(AuditRun).where(AuditRun.status == "Completed")):
            if r.template_id in ids and r.period in acc:
                acc[r.period][0] += r.yes_count
                acc[r.period][1] += r.yes_count + r.no_count
    return {p: (v[0], v[1]) for p, v in acc.items() if v[1]}


def series(db: Session, ind: Indicator, periods: list[str]) -> list[dict]:
    if ind.auto:
        raw = _auto_rows(db, ind.auto, periods)
        notes = {}
        # months with no records in the system fall back to imported history, if any
        for v in db.scalars(select(IndicatorValue).where(IndicatorValue.indicator_id == ind.id, IndicatorValue.period.in_(periods))):
            if v.period not in raw:
                raw[v.period], notes[v.period] = (v.numerator, v.denominator), v.note
    else:
        vals = {v.period: v for v in db.scalars(select(IndicatorValue).where(IndicatorValue.indicator_id == ind.id, IndicatorValue.period.in_(periods)))}
        raw = {p: (v.numerator, v.denominator) for p, v in vals.items()}
        notes = {p: v.note for p, v in vals.items()}
    out = []
    for p in periods:
        if p in raw and raw[p][1]:
            n, d = raw[p]
            out.append({"period": p, "numerator": round(n, 2), "denominator": round(d, 2), "value": round(n / d * ind.multiplier, 2), "note": notes.get(p, "")})
    return out


def rag(ind: Indicator, value: float | None) -> str:
    if value is None:
        return "neutral"
    amber = ind.amber if ind.amber is not None else ind.target
    if ind.direction == "higher":
        return "green" if value >= ind.target else "amber" if value >= amber else "red"
    return "green" if value <= ind.target else "amber" if value <= amber else "red"


def run_chart(points: list[dict]) -> dict:
    """Median line and shift rule: six or more consecutive points on the same side of the median (points on the median are ignored)."""
    if not points:
        return {"median": None, "shift": None}
    med = median(p["value"] for p in points)
    run, side, best = [], 0, None
    for i, p in enumerate(points):
        s = (p["value"] > med) - (p["value"] < med)
        if s == 0:
            continue
        if s != side:
            run, side = [], s
        run.append(i)
        if len(run) >= 6:  # keep the most recent shift
            best = {"indexes": list(run), "side": "above" if s > 0 else "below", "length": len(run)}
    return {"median": round(med, 2), "shift": best}


def status_label(ind: Indicator, shift: dict | None) -> str | None:
    if not shift:
        return None
    worse = (shift["side"] == "above") == (ind.direction == "lower")
    return "worsening" if worse else "improving"

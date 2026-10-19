import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import AuditAnswer, AuditRun, AuditTemplate, Department, QualityAction, User, now
from ..security import can, require
from ..services import hospital_tz
from .accreditation import evidence_root

router = APIRouter(prefix="/api/audits", tags=["audits"])
PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def month_end(period: str, db: Session) -> datetime:
    y, m = map(int, period.split("-"))
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return datetime.combine(nxt, datetime.min.time(), hospital_tz(db)) - timedelta(minutes=1)


def valid_period(p: str):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", p):
        raise HTTPException(422, "Month must be written as YYYY-MM.")


def names(db):
    return {u.id: u.name for u in db.scalars(select(User))}, {d.id: d.name for d in db.scalars(select(Department))}, {t.id: t for t in db.scalars(select(AuditTemplate))}


def run_row(r: AuditRun, users, depts, tpls):
    t = tpls.get(r.template_id)
    return {"id": r.id, "template_id": r.template_id, "template": t.name if t else "", "target": t.target if t else None, "department_id": r.department_id,
            "department": depts.get(r.department_id, "—"), "unit": r.unit, "period": r.period, "due_at": r.due_at, "status": r.status,
            "overdue": r.status != "Completed" and r.due_at < now(), "auditor_id": r.auditor_id, "auditor": users.get(r.auditor_id, "Unassigned"),
            "completed_at": r.completed_at, "score": r.score, "yes": r.yes_count, "no": r.no_count,
            "on_target": (r.score is not None and t is not None and r.score >= t.target)}


# ---------- templates
@router.get("/templates")
def templates(db: Session = Depends(get_db), user: User = Depends(require("audits"))):
    return [{"id": t.id, "name": t.name, "description": t.description, "items": t.items, "target": t.target, "active": t.active}
            for t in db.scalars(select(AuditTemplate).order_by(AuditTemplate.name))]


class TemplateBody(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = ""
    items: list[str] = Field(min_length=1)
    target: float = Field(ge=1, le=100)
    active: bool = True


def make_items(lines: list[str]):
    clean = [x.strip() for x in lines if x.strip()]
    if not clean:
        raise HTTPException(422, "Add at least one checklist item.")
    return [{"key": f"i{n}", "text": t} for n, t in enumerate(clean, 1)]


@router.post("/templates")
def create_template(b: TemplateBody, db: Session = Depends(get_db), user: User = Depends(require("audits", "admin"))):
    t = AuditTemplate(name=b.name.strip(), description=b.description.strip(), items=make_items(b.items), target=b.target, active=b.active)
    db.add(t)
    db.flush()
    audit.log(db, user, "audits", "template_add", "template", t.id, f"Audit template created: {t.name}")
    db.commit()
    return {"id": t.id}


@router.put("/templates/{tid}")
def edit_template(tid: str, b: TemplateBody, db: Session = Depends(get_db), user: User = Depends(require("audits", "admin"))):
    t = db.get(AuditTemplate, tid)
    if not t:
        raise HTTPException(404, "Template not found")
    before = {"name": t.name, "target": t.target, "items": len(t.items), "active": t.active}
    old = {i["text"]: i["key"] for i in t.items}
    # keep existing keys for unchanged wording so past answers stay linked to their question
    keys = iter(range(1, 1000))
    items, used = [], set()
    for text in [x.strip() for x in b.items if x.strip()]:
        key = old.get(text)
        if not key or key in used:
            key = f"n{next(keys)}{uuid.uuid4().hex[:4]}"
        used.add(key)
        items.append({"key": key, "text": text})
    if not items:
        raise HTTPException(422, "Add at least one checklist item.")
    t.name, t.description, t.items, t.target, t.active = b.name.strip(), b.description.strip(), items, b.target, b.active
    audit.log(db, user, "audits", "template_edit", "template", t.id, f"Audit template updated: {t.name}", before, {"name": t.name, "target": t.target, "items": len(items), "active": t.active})
    db.commit()
    return {"ok": True}


# ---------- schedule and runs
class Unit(BaseModel):
    department_id: str | None = None
    unit: str = ""
    auditor_id: str | None = None


class Schedule(BaseModel):
    template_id: str
    units: list[Unit] = Field(min_length=1)
    periods: list[str] = Field(min_length=1)


@router.post("/schedule")
def schedule(b: Schedule, db: Session = Depends(get_db), user: User = Depends(require("audits", "approve"))):
    t = db.get(AuditTemplate, b.template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    for p in b.periods:
        valid_period(p)
    made = 0
    for p in b.periods:
        for u in b.units:
            if db.scalar(select(AuditRun).where(AuditRun.template_id == t.id, AuditRun.period == p, AuditRun.unit == u.unit, AuditRun.department_id == u.department_id)):
                continue
            db.add(AuditRun(template_id=t.id, department_id=u.department_id, unit=u.unit, period=p, due_at=month_end(p, db), auditor_id=u.auditor_id))
            made += 1
    audit.log(db, user, "audits", "schedule", "template", t.id, f"{made} audits scheduled for {t.name}")
    db.commit()
    return {"created": made}


@router.get("/runs")
def runs(page: int = 1, size: int = Query(20, le=200), template_id: str | None = None, department_id: str | None = None, status: str | None = None,
         period: str | None = None, overdue: bool | None = None, mine: bool | None = None, db: Session = Depends(get_db), user: User = Depends(require("audits"))):
    stmt = select(AuditRun)
    for col, v in ((AuditRun.template_id, template_id), (AuditRun.department_id, department_id), (AuditRun.status, status), (AuditRun.period, period)):
        if v:
            stmt = stmt.where(col == v)
    if overdue:
        stmt = stmt.where(AuditRun.status != "Completed", AuditRun.due_at < now())
    if mine:
        stmt = stmt.where(AuditRun.auditor_id == user.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(AuditRun.status.desc(), AuditRun.period.desc(), AuditRun.unit).offset((page - 1) * size).limit(size)
    users, depts, tpls = names(db)
    return {"total": total, "items": [run_row(r, users, depts, tpls) for r in db.scalars(stmt)]}


def get_run(db, rid) -> AuditRun:
    r = db.get(AuditRun, rid)
    if not r:
        raise HTTPException(404, "Audit not found")
    return r


def can_work(user: User, r: AuditRun) -> bool:
    return can(user, "audits", "approve") or r.auditor_id == user.id


@router.get("/runs/{rid}")
def run_detail(rid: str, db: Session = Depends(get_db), user: User = Depends(require("audits"))):
    r = get_run(db, rid)
    users, depts, tpls = names(db)
    t = tpls[r.template_id]
    ans = {a.item_key: a for a in db.scalars(select(AuditAnswer).where(AuditAnswer.run_id == rid))}
    items = []
    for it in t.items:
        a = ans.get(it["key"])
        act = db.get(QualityAction, a.action_id) if a and a.action_id else None
        items.append({"key": it["key"], "text": it["text"], "result": a.result if a else None, "comment": a.comment if a else "", "has_photo": bool(a and a.photo_path),
                      "action": {"id": act.id, "text": act.text, "owner": users.get(act.owner_id, "Unassigned"), "due_at": act.due_at, "status": act.status} if act else None})
    return run_row(r, users, depts, tpls) | {"description": t.description, "comment": r.comment, "items": items, "can_work": can_work(user, r),
                                              "answered": sum(i["result"] is not None for i in items)}


class AnswerBody(BaseModel):
    key: str
    result: str
    comment: str = ""


class Answers(BaseModel):
    answers: list[AnswerBody]


@router.put("/runs/{rid}/answers")
def save_answers(rid: str, b: Answers, db: Session = Depends(get_db), user: User = Depends(require("audits", "create"))):
    r = get_run(db, rid)
    if not can_work(user, r):
        raise HTTPException(403, "Only the assigned auditor or the Quality team can record this audit.")
    if r.status == "Completed":
        raise HTTPException(409, "This audit is completed.")
    keys = {i["key"] for i in db.get(AuditTemplate, r.template_id).items}
    have = {a.item_key: a for a in db.scalars(select(AuditAnswer).where(AuditAnswer.run_id == rid))}
    for a in b.answers:
        if a.key not in keys or a.result not in ("yes", "no", "na"):
            raise HTTPException(422, "Each answer must be yes, no or na for a question on this checklist.")
        row = have.get(a.key) or AuditAnswer(run_id=rid, item_key=a.key, result=a.result)
        row.result, row.comment = a.result, a.comment.strip()
        if a.key not in have:
            db.add(row)
    db.commit()
    return {"ok": True}


@router.post("/runs/{rid}/photo/{key}")
async def upload_photo(rid: str, key: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require("audits", "create"))):
    r = get_run(db, rid)
    if not can_work(user, r):
        raise HTTPException(403, "Only the assigned auditor or the Quality team can record this audit.")
    a = db.scalar(select(AuditAnswer).where(AuditAnswer.run_id == rid, AuditAnswer.item_key == key))
    if not a:
        raise HTTPException(422, "Answer the question before adding a photo.")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in PHOTO_TYPES:
        raise HTTPException(422, "Upload a JPG, PNG or WebP photo.")
    data = await file.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(422, "Photos can be up to 8 MB.")
    rel = f"audits/{rid}/{key}-{uuid.uuid4().hex[:6]}{ext}"
    dest = evidence_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    a.photo_path = rel
    db.commit()
    return {"ok": True}


@router.get("/runs/{rid}/photo/{key}")
def get_photo(rid: str, key: str, db: Session = Depends(get_db), user: User = Depends(require("audits"))):
    a = db.scalar(select(AuditAnswer).where(AuditAnswer.run_id == rid, AuditAnswer.item_key == key))
    p = (evidence_root() / a.photo_path).resolve() if a and a.photo_path else None
    if not p or not p.is_file() or evidence_root().resolve() not in p.parents:
        raise HTTPException(404, "Photo not found")
    return FileResponse(p)


class Complete(BaseModel):
    comment: str = ""


@router.post("/runs/{rid}/complete")
def complete(rid: str, b: Complete, db: Session = Depends(get_db), user: User = Depends(require("audits", "create"))):
    r = get_run(db, rid)
    if not can_work(user, r):
        raise HTTPException(403, "Only the assigned auditor or the Quality team can complete this audit.")
    if r.status == "Completed":
        raise HTTPException(409, "This audit is already completed.")
    t = db.get(AuditTemplate, r.template_id)
    ans = db.scalars(select(AuditAnswer).where(AuditAnswer.run_id == rid)).all()
    if len(ans) < len(t.items):
        raise HTTPException(422, f"Answer every question before completing ({len(ans)} of {len(t.items)} answered).")
    r.yes_count, r.no_count = sum(a.result == "yes" for a in ans), sum(a.result == "no" for a in ans)
    r.score = round(100 * r.yes_count / (r.yes_count + r.no_count), 1) if (r.yes_count + r.no_count) else None
    if r.score is None:
        raise HTTPException(422, "At least one question must be answered Yes or No.")
    r.status, r.completed_at, r.comment = "Completed", now(), b.comment.strip()
    r.auditor_id = r.auditor_id or user.id
    audit.log(db, user, "audits", "complete", "audit", r.id, f"{t.name} completed for {r.unit or 'all areas'} {r.period}: {r.score}%", None, {"score": r.score})
    db.commit()
    return {"score": r.score, "on_target": r.score >= t.target}


class ActionBody(BaseModel):
    text: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None


@router.post("/runs/{rid}/answers/{key}/action")
def raise_action(rid: str, key: str, b: ActionBody, db: Session = Depends(get_db), user: User = Depends(require("audits", "create"))):
    """A 'No' answer can raise a corrective action in one click."""
    r = get_run(db, rid)
    t = db.get(AuditTemplate, r.template_id)
    a = db.scalar(select(AuditAnswer).where(AuditAnswer.run_id == rid, AuditAnswer.item_key == key))
    if not a or a.result != "no":
        raise HTTPException(422, "Actions can only be raised for questions answered No.")
    if a.action_id:
        raise HTTPException(409, "An action already exists for this question.")
    text = (b.text or "").strip() or next(f"Correct: {i['text']} ({t.name}, {r.unit or 'all areas'} {r.period})" for i in t.items if i["key"] == key)
    act = QualityAction(text=text[:2000], source_type="audit", source_id=rid, department_id=r.department_id, owner_id=b.owner_id or user.id,
                        due_at=b.due_at or now() + timedelta(days=14), created_by=user.name)
    db.add(act)
    db.flush()
    a.action_id = act.id
    audit.log(db, user, "audits", "action_add", "action", act.id, f"Action raised from audit {t.name} {r.period}")
    db.commit()
    return {"id": act.id}


# ---------- compliance over time
@router.get("/compliance")
def compliance(template_id: str, months: int = Query(6, ge=1, le=24), db: Session = Depends(get_db), user: User = Depends(require("audits"))):
    t = db.get(AuditTemplate, template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    _, depts, _ = names(db)
    today = date.today()
    periods = []
    y, m = today.year, today.month
    for _ in range(months):
        periods.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    periods.reverse()
    rows = db.scalars(select(AuditRun).where(AuditRun.template_id == template_id, AuditRun.status == "Completed", AuditRun.period.in_(periods))).all()

    def pct(rs):
        yes, no = sum(r.yes_count for r in rs), sum(r.no_count for r in rs)
        return round(100 * yes / (yes + no), 1) if yes + no else None
    overall = [{"period": p, "score": pct([r for r in rows if r.period == p]), "audits": len([r for r in rows if r.period == p])} for p in periods]
    units: dict = {}
    for r in rows:
        units.setdefault(r.unit or depts.get(r.department_id, "—"), []).append(r)
    by_unit = []
    for name, rs in units.items():
        series = [{"period": p, "score": pct([r for r in rs if r.period == p])} for p in periods]
        scored = [s["score"] for s in series if s["score"] is not None]
        by_unit.append({"unit": name, "series": series, "latest": scored[-1] if scored else None, "change": round(scored[-1] - scored[0], 1) if len(scored) > 1 else None,
                        "department": depts.get(rs[0].department_id, "—")})
    by_unit.sort(key=lambda u: (u["latest"] is None, u["latest"]))
    return {"template": {"id": t.id, "name": t.name, "target": t.target}, "periods": periods, "overall": overall, "units": by_unit}

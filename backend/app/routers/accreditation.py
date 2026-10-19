import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import settings as cfg
from ..db import get_db
from ..defaults import ELEMENT_STATUSES
from ..models import (AuditRun, AuditTemplate, Capa, Evidence, Incident, QualityAction, StandardChapter, StandardElement, TracerResult,
                      TracerRun, User, now)
from ..security import require
from ..services import get_setting, put_setting, readiness

router = APIRouter(prefix="/api/accreditation", tags=["accreditation"])
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx"}
MAX_BYTES = 10 * 1024 * 1024


def evidence_root() -> Path:
    p = Path(cfg.evidence_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def people(db):
    return {u.id: u.name for u in db.scalars(select(User))}


def el_row(e: StandardElement, ch: StandardChapter, users: dict, evidence_n: int = 0, action_n: int = 0):
    return {"id": e.id, "code": e.code, "text": e.text, "standard_code": e.standard_code, "standard_title": e.standard_title,
            "chapter_id": e.chapter_id, "chapter": f"{ch.code} {ch.name}", "owner_id": e.owner_id, "owner": users.get(e.owner_id, "Unassigned"),
            "status": e.status, "last_reviewed_at": e.last_reviewed_at, "note": e.note, "evidence_count": evidence_n, "open_actions": action_n,
            "review_overdue": e.status != "Not applicable" and (e.last_reviewed_at is None or e.last_reviewed_at < now() - timedelta(days=180))}


def counts(db, model, col, ids=None):
    stmt = select(col, func.count()).group_by(col)
    if ids is not None:
        stmt = stmt.where(col.in_(ids))
    return {k: v for k, v in db.execute(stmt)}


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(require("accreditation"))):
    cfgv = get_setting(db, "accreditation")
    sd = date.fromisoformat(cfgv["survey_date"]) if cfgv.get("survey_date") else None
    chapters = db.scalars(select(StandardChapter).order_by(StandardChapter.position)).all()
    users = people(db)
    gaps = []
    ev_n = counts(db, Evidence, Evidence.element_id)
    act_n = {k: v for k, v in db.execute(select(QualityAction.element_id, func.count()).where(QualityAction.status != "Completed").group_by(QualityAction.element_id))}
    chap = {c.id: c for c in chapters}
    for e in db.scalars(select(StandardElement).where(StandardElement.status.in_(["Not met", "Partially met"])).order_by(StandardElement.position)):
        gaps.append(el_row(e, chap[e.chapter_id], users, ev_n.get(e.id, 0), act_n.get(e.id, 0)))
    gaps.sort(key=lambda g: (g["status"] != "Not met", g["code"]))
    met_no_evidence = db.scalar(select(func.count()).select_from(StandardElement).where(StandardElement.status == "Met", ~StandardElement.id.in_(select(Evidence.element_id))))
    return {"name": cfgv.get("name", ""), "survey_date": cfgv.get("survey_date") or None, "days_left": (sd - date.today()).days if sd else None,
            "readiness": readiness(db), "met_without_evidence": met_no_evidence,
            "chapters": [{"id": c.id, "code": c.code, "name": c.name} | readiness(db, c.id) for c in chapters], "gaps": gaps}


class SurveyBody(BaseModel):
    survey_date: str
    name: str = ""


@router.put("/survey-date")
def set_survey(b: SurveyBody, db: Session = Depends(get_db), user: User = Depends(require("accreditation", "approve"))):
    try:
        date.fromisoformat(b.survey_date)
    except ValueError:
        raise HTTPException(422, "Dates must be written as YYYY-MM-DD.")
    before = get_setting(db, "accreditation")
    put_setting(db, "accreditation", {"name": b.name or before.get("name", ""), "survey_date": b.survey_date})
    audit.log(db, user, "accreditation", "survey_date", "setting", "accreditation", "Survey date updated", before, {"survey_date": b.survey_date})
    db.commit()
    return {"ok": True}


@router.get("/chapters/{cid}")
def chapter(cid: str, db: Session = Depends(get_db), user: User = Depends(require("accreditation"))):
    ch = db.get(StandardChapter, cid)
    if not ch:
        raise HTTPException(404, "Chapter not found")
    users = people(db)
    els = db.scalars(select(StandardElement).where(StandardElement.chapter_id == cid).order_by(StandardElement.position)).all()
    ev_n = counts(db, Evidence, Evidence.element_id, [e.id for e in els])
    act_n = {k: v for k, v in db.execute(select(QualityAction.element_id, func.count()).where(QualityAction.status != "Completed").group_by(QualityAction.element_id))}
    standards: dict = {}
    for e in els:
        s = standards.setdefault(e.standard_code, {"code": e.standard_code, "title": e.standard_title, "elements": []})
        s["elements"].append(el_row(e, ch, users, ev_n.get(e.id, 0), act_n.get(e.id, 0)))
    return {"id": ch.id, "code": ch.code, "name": ch.name, "readiness": readiness(db, cid), "standards": list(standards.values())}


@router.get("/elements")
def elements(chapter_id: str | None = None, status: str | None = None, mine: bool | None = None, q: str | None = None,
             db: Session = Depends(get_db), user: User = Depends(require("accreditation"))):
    stmt = select(StandardElement, StandardChapter).join(StandardChapter, StandardChapter.id == StandardElement.chapter_id)
    if chapter_id:
        stmt = stmt.where(StandardElement.chapter_id == chapter_id)
    if status:
        stmt = stmt.where(StandardElement.status == status)
    if mine:
        stmt = stmt.where(StandardElement.owner_id == user.id)
    if q:
        stmt = stmt.where(StandardElement.text.ilike(f"%{q}%") | StandardElement.code.ilike(f"%{q}%"))
    users = people(db)
    return [el_row(e, c, users) for e, c in db.execute(stmt.order_by(StandardChapter.position, StandardElement.position))]


def get_element(db, eid) -> StandardElement:
    e = db.get(StandardElement, eid)
    if not e:
        raise HTTPException(404, "Element not found")
    return e


@router.get("/elements/{eid}")
def element(eid: str, db: Session = Depends(get_db), user: User = Depends(require("accreditation"))):
    e = get_element(db, eid)
    ch = db.get(StandardChapter, e.chapter_id)
    users = people(db)
    evs = db.scalars(select(Evidence).where(Evidence.element_id == eid).order_by(Evidence.created_at.desc())).all()
    acts = db.scalars(select(QualityAction).where(QualityAction.element_id == eid).order_by(QualityAction.due_at)).all()
    return el_row(e, ch, users, len(evs)) | {
        "evidence": [{"id": v.id, "kind": v.kind, "title": v.title, "filename": v.filename, "source_id": v.source_id, "added_by": v.added_by, "created_at": v.created_at} for v in evs],
        "actions": [action_row(a, users) for a in acts]}


def action_row(a: QualityAction, users: dict):
    return {"id": a.id, "text": a.text, "source_type": a.source_type, "element_id": a.element_id, "owner_id": a.owner_id, "owner": users.get(a.owner_id, "Unassigned"),
            "due_at": a.due_at, "status": a.status, "overdue": a.status != "Completed" and a.due_at < now()}


class ElementEdit(BaseModel):
    status: str | None = None
    owner_id: str | None = None
    note: str | None = None


@router.put("/elements/{eid}")
def edit_element(eid: str, b: ElementEdit, db: Session = Depends(get_db), user: User = Depends(require("accreditation", "create"))):
    e = get_element(db, eid)
    if b.status and b.status not in ELEMENT_STATUSES:
        raise HTTPException(422, "Status must be Met, Partially met, Not met or Not applicable.")
    before = {"status": e.status, "owner_id": e.owner_id, "note": e.note}
    if b.status:
        e.status = b.status
    if b.owner_id is not None:
        e.owner_id = b.owner_id or None
    if b.note is not None:
        e.note = b.note.strip()
    e.last_reviewed_at = now()
    audit.log(db, user, "accreditation", "element", "element", e.id, f"{e.code} reviewed: {e.status}", before, {"status": e.status, "owner_id": e.owner_id, "note": e.note})
    db.commit()
    return {"ok": True}


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]", "_", Path(name).name)[:120] or "file"


@router.post("/elements/{eid}/evidence")
async def upload_evidence(eid: str, file: UploadFile = File(...), title: str = Form(""), mark_met: bool = Form(False),
                          db: Session = Depends(get_db), user: User = Depends(require("accreditation", "create"))):
    e = get_element(db, eid)
    name = safe_name(file.filename or "file")
    if Path(name).suffix.lower() not in ALLOWED:
        raise HTTPException(422, "Upload a PDF, image, Word or Excel file.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(422, "Files can be up to 10 MB.")
    rel = f"{e.id}/{uuid.uuid4().hex[:8]}-{name}"
    dest = evidence_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    ev = Evidence(element_id=e.id, kind="file", title=title.strip() or name, filename=name, path=rel, added_by=user.name)
    db.add(ev)
    if mark_met:
        e.status, e.last_reviewed_at = "Met", now()
    audit.log(db, user, "accreditation", "evidence_add", "element", e.id, f"Evidence added to {e.code}: {ev.title}")
    db.commit()
    return {"id": ev.id}


class AttachBody(BaseModel):
    source_type: str  # capa | audit_run
    source_id: str
    mark_met: bool = False


@router.post("/elements/{eid}/attach")
def attach(eid: str, b: AttachBody, db: Session = Depends(get_db), user: User = Depends(require("accreditation", "create"))):
    """Attach a closed corrective action or a completed audit as evidence in one click."""
    e = get_element(db, eid)
    if b.source_type == "capa":
        c = db.get(Capa, b.source_id)
        inc = db.get(Incident, c.incident_id) if c else None
        if not c or c.status != "Completed":
            raise HTTPException(422, "Only a completed corrective action can be used as evidence.")
        title = f"Corrective action {inc.number}: {c.action[:140]}"
    elif b.source_type == "audit_run":
        r = db.get(AuditRun, b.source_id)
        t = db.get(AuditTemplate, r.template_id) if r else None
        if not r or r.status != "Completed":
            raise HTTPException(422, "Only a completed audit can be used as evidence.")
        title = f"Audit: {t.name}, {r.unit or 'all areas'}, {r.period} ({r.score:.0f}% compliance)"
    else:
        raise HTTPException(422, "Evidence source must be capa or audit_run.")
    if db.scalar(select(Evidence).where(Evidence.element_id == e.id, Evidence.kind == b.source_type, Evidence.source_id == b.source_id)):
        raise HTTPException(409, "This is already attached to the element.")
    db.add(Evidence(element_id=e.id, kind=b.source_type, title=title, source_id=b.source_id, added_by=user.name))
    if b.mark_met:
        e.status, e.last_reviewed_at = "Met", now()
    audit.log(db, user, "accreditation", "evidence_add", "element", e.id, f"Evidence linked to {e.code}: {title[:200]}")
    db.commit()
    return {"ok": True, "readiness": readiness(db)}


@router.get("/evidence/{vid}/download")
def download(vid: str, db: Session = Depends(get_db), user: User = Depends(require("accreditation"))):
    v = db.get(Evidence, vid)
    p = (evidence_root() / v.path).resolve() if v and v.path else None
    if not v or not p or not p.is_file() or evidence_root().resolve() not in p.parents:
        raise HTTPException(404, "File not found")
    return FileResponse(p, filename=v.filename)


@router.delete("/evidence/{vid}")
def remove_evidence(vid: str, db: Session = Depends(get_db), user: User = Depends(require("accreditation", "approve"))):
    v = db.get(Evidence, vid)
    if not v:
        raise HTTPException(404, "Evidence not found")
    audit.log(db, user, "accreditation", "evidence_remove", "element", v.element_id, f"Evidence removed: {v.title[:200]}")
    db.delete(v)
    db.commit()
    return {"ok": True}


# ---------- tracer (mock survey)
class TracerStart(BaseModel):
    chapter_id: str


def tracer_out(db, run: TracerRun):
    ch = db.get(StandardChapter, run.chapter_id)
    users = people(db)
    results = {r.element_id: r for r in db.scalars(select(TracerResult).where(TracerResult.run_id == run.id))}
    out = []
    for e in db.scalars(select(StandardElement).where(StandardElement.chapter_id == run.chapter_id).order_by(StandardElement.position)):
        r = results.get(e.id)
        act = db.get(QualityAction, r.action_id) if r and r.action_id else None
        out.append(el_row(e, ch, users) | {"result": r.result if r else None, "finding": r.note if r else "", "action": action_row(act, users) if act else None})
    done = sum(x["result"] is not None for x in out)
    return {"id": run.id, "chapter": {"id": ch.id, "code": ch.code, "name": ch.name}, "started_at": run.started_at, "completed_at": run.completed_at,
            "progress": {"done": done, "total": len(out)}, "elements": out}


@router.post("/tracers")
def start_tracer(b: TracerStart, db: Session = Depends(get_db), user: User = Depends(require("accreditation", "create"))):
    if not db.get(StandardChapter, b.chapter_id):
        raise HTTPException(404, "Chapter not found")
    run = TracerRun(chapter_id=b.chapter_id, started_by=user.name)
    db.add(run)
    audit.log(db, user, "accreditation", "tracer_start", "chapter", b.chapter_id, "Mock survey started")
    db.commit()
    return {"id": run.id}


@router.get("/tracers/{rid}")
def get_tracer(rid: str, db: Session = Depends(get_db), user: User = Depends(require("accreditation"))):
    run = db.get(TracerRun, rid)
    if not run:
        raise HTTPException(404, "Mock survey not found")
    return tracer_out(db, run)


@router.get("/tracers")
def list_tracers(db: Session = Depends(get_db), user: User = Depends(require("accreditation"))):
    out = []
    for r in db.scalars(select(TracerRun).order_by(TracerRun.started_at.desc()).limit(20)):
        ch = db.get(StandardChapter, r.chapter_id)
        n = db.scalar(select(func.count()).select_from(TracerResult).where(TracerResult.run_id == r.id))
        out.append({"id": r.id, "chapter": f"{ch.code} {ch.name}", "started_by": r.started_by, "started_at": r.started_at, "completed_at": r.completed_at, "recorded": n})
    return out


class TracerResultBody(BaseModel):
    result: str
    note: str = ""


@router.put("/tracers/{rid}/results/{eid}")
def record_result(rid: str, eid: str, b: TracerResultBody, db: Session = Depends(get_db), user: User = Depends(require("accreditation", "create"))):
    run = db.get(TracerRun, rid)
    e = get_element(db, eid)
    if not run or run.completed_at or e.chapter_id != run.chapter_id:
        raise HTTPException(404, "Mock survey not found or already completed")
    if b.result not in ELEMENT_STATUSES:
        raise HTTPException(422, "Result must be Met, Partially met, Not met or Not applicable.")
    r = db.scalar(select(TracerResult).where(TracerResult.run_id == rid, TracerResult.element_id == eid))
    if not r:
        r = TracerResult(run_id=rid, element_id=eid, result=b.result)
        db.add(r)
    r.result, r.note = b.result, b.note.strip()
    before = e.status
    e.status, e.last_reviewed_at = b.result, now()  # the readiness figure follows what the surveyor found
    audit.log(db, user, "accreditation", "tracer_result", "element", e.id, f"Mock survey: {e.code} {b.result}", {"status": before}, {"status": b.result, "finding": r.note})
    db.commit()
    return {"ok": True}


class TracerAction(BaseModel):
    text: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None


@router.post("/tracers/{rid}/results/{eid}/action")
def finding_to_action(rid: str, eid: str, b: TracerAction, db: Session = Depends(get_db), user: User = Depends(require("accreditation", "create"))):
    """Two clicks from a finding to an action: defaults to the element owner, due in 30 days."""
    r = db.scalar(select(TracerResult).where(TracerResult.run_id == rid, TracerResult.element_id == eid))
    e = get_element(db, eid)
    if not r or r.result in ("Met", "Not applicable"):
        raise HTTPException(422, "Record a finding (partially met or not met) first.")
    if r.action_id:
        raise HTTPException(409, "An action already exists for this finding.")
    text = (b.text or "").strip() or f"Close the gap for {e.code}: {r.note or e.text}"
    a = QualityAction(text=text[:2000], source_type="tracer", source_id=rid, element_id=e.id, owner_id=b.owner_id or e.owner_id or user.id,
                      due_at=b.due_at or now() + timedelta(days=30), created_by=user.name)
    db.add(a)
    db.flush()
    r.action_id = a.id
    audit.log(db, user, "accreditation", "action_add", "action", a.id, f"Action raised from mock survey finding on {e.code}")
    db.commit()
    return {"id": a.id}


@router.post("/tracers/{rid}/complete")
def complete_tracer(rid: str, db: Session = Depends(get_db), user: User = Depends(require("accreditation", "create"))):
    run = db.get(TracerRun, rid)
    if not run:
        raise HTTPException(404, "Mock survey not found")
    run.completed_at = run.completed_at or now()
    audit.log(db, user, "accreditation", "tracer_complete", "chapter", run.chapter_id, "Mock survey completed")
    db.commit()
    return {"ok": True}

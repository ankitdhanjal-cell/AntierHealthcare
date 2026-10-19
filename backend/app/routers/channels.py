import io

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import settings as cfg
from ..db import get_db
from ..models import Department, FeedbackChannel, FeedbackResponse, User
from ..security import require

router = APIRouter(prefix="/api/channels", tags=["channels"])


def url(ch: FeedbackChannel) -> str:
    return f"{cfg.public_web_url}/f/c/{ch.token}"


def row(ch: FeedbackChannel, depts: dict, n: int = 0):
    return {"id": ch.id, "name": ch.name, "kind": ch.kind, "department_id": ch.department_id, "department": depts.get(ch.department_id, "—"), "active": ch.active, "url": url(ch), "responses": n}


@router.get("")
def list_channels(db: Session = Depends(get_db), user: User = Depends(require("settings"))):
    depts = {d.id: d.name for d in db.scalars(select(Department))}
    counts = {k: v for k, v in db.execute(select(FeedbackResponse.channel_id, func.count()).where(FeedbackResponse.channel_id.isnot(None)).group_by(FeedbackResponse.channel_id))}
    return [row(c, depts, counts.get(c.id, 0)) for c in db.scalars(select(FeedbackChannel).order_by(FeedbackChannel.kind, FeedbackChannel.name))]


class Body(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kind: str = "ward"
    department_id: str | None = None
    active: bool = True


@router.post("")
def create(b: Body, db: Session = Depends(get_db), user: User = Depends(require("settings", "admin"))):
    if b.kind not in ("ward", "clinic"):
        raise HTTPException(422, "Type must be ward or clinic.")
    ch = FeedbackChannel(name=b.name.strip(), kind=b.kind, department_id=b.department_id, active=b.active)
    db.add(ch)
    db.flush()
    audit.log(db, user, "settings", "channel_add", "channel", ch.id, f"Feedback QR code created: {ch.name}")
    db.commit()
    return {"id": ch.id}


@router.put("/{cid}")
def edit(cid: str, b: Body, db: Session = Depends(get_db), user: User = Depends(require("settings", "admin"))):
    ch = db.get(FeedbackChannel, cid)
    if not ch:
        raise HTTPException(404, "QR code not found")
    ch.name, ch.kind, ch.department_id, ch.active = b.name.strip(), b.kind, b.department_id, b.active
    audit.log(db, user, "settings", "channel_edit", "channel", ch.id, f"Feedback QR code updated: {ch.name}")
    db.commit()
    return {"ok": True}


@router.get("/{cid}/qr.svg")
def qr(cid: str, db: Session = Depends(get_db), user: User = Depends(require("settings"))):
    ch = db.get(FeedbackChannel, cid)
    if not ch:
        raise HTTPException(404, "QR code not found")
    img = qrcode.make(url(ch), image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")

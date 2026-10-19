from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import QualityAction, User, now
from ..security import can, current_user, dept_scope

router = APIRouter(prefix="/api/actions", tags=["actions"])


def allowed(user: User):
    if not (can(user, "accreditation") or can(user, "audits")):
        raise HTTPException(403, "Your role does not allow access to quality actions.")


def row(a: QualityAction, users: dict):
    return {"id": a.id, "text": a.text, "source_type": a.source_type, "element_id": a.element_id, "owner_id": a.owner_id, "owner": users.get(a.owner_id, "Unassigned"),
            "due_at": a.due_at, "status": a.status, "completed_at": a.completed_at, "overdue": a.status != "Completed" and a.due_at < now()}


@router.get("")
def list_actions(mine: bool | None = None, status: str | None = None, overdue: bool | None = None, source_type: str | None = None,
                 db: Session = Depends(get_db), user: User = Depends(current_user)):
    allowed(user)
    stmt = select(QualityAction)
    scope = dept_scope(user)
    if scope is not None and not can(user, "accreditation", "approve"):  # others see their own actions and their departments'
        stmt = stmt.where(or_(QualityAction.owner_id == user.id, QualityAction.department_id.in_(scope)))
    if mine:
        stmt = stmt.where(QualityAction.owner_id == user.id)
    if status:
        stmt = stmt.where(QualityAction.status == status)
    if source_type:
        stmt = stmt.where(QualityAction.source_type == source_type)
    if overdue:
        stmt = stmt.where(QualityAction.status != "Completed", QualityAction.due_at < now())
    users = {u.id: u.name for u in db.scalars(select(User))}
    return [row(a, users) for a in db.scalars(stmt.order_by(QualityAction.due_at))]


class Create(BaseModel):
    text: str = Field(min_length=5, max_length=2000)
    element_id: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None


@router.post("")
def create(b: Create, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """A manual action against an accreditation gap."""
    if not can(user, "accreditation", "create"):
        raise HTTPException(403, "Your role cannot create accreditation actions.")
    a = QualityAction(text=b.text.strip(), source_type="gap", element_id=b.element_id, owner_id=b.owner_id or user.id,
                      due_at=b.due_at or now() + timedelta(days=30), created_by=user.name)
    db.add(a)
    db.flush()
    audit.log(db, user, "accreditation", "action_add", "action", a.id, "Accreditation action created")
    db.commit()
    return {"id": a.id}


class Edit(BaseModel):
    status: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None


@router.put("/{aid}")
def edit(aid: str, b: Edit, db: Session = Depends(get_db), user: User = Depends(current_user)):
    a = db.get(QualityAction, aid)
    if not a:
        raise HTTPException(404, "Action not found")
    if not (a.owner_id == user.id or can(user, "accreditation", "create") or can(user, "audits", "create")):
        raise HTTPException(403, "Only the owner or the Quality team can update this action.")
    if b.status and b.status not in ("Open", "In progress", "Completed"):
        raise HTTPException(422, "Status must be Open, In progress or Completed.")
    before = {"status": a.status, "owner_id": a.owner_id, "due_at": a.due_at}
    if b.owner_id:
        a.owner_id = b.owner_id
    if b.due_at:
        a.due_at, a.overdue_notified = b.due_at, False
    if b.status:
        a.status = b.status
        a.completed_at = now() if b.status == "Completed" else None
    audit.log(db, user, "accreditation", "action_update", "action", a.id, f"Action updated: {a.status}", before, {"status": a.status, "owner_id": a.owner_id, "due_at": a.due_at})
    db.commit()
    return {"ok": True}

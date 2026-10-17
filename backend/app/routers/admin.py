from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import settings
from ..db import get_db
from ..models import Department, Role, Tenant, User
from ..security import make_token, require
from ..services import DEFAULTS, get_setting, put_setting, send_email

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/departments")
def departments(db: Session = Depends(get_db), u: User = Depends(require("dashboard"))):
    return [{"id": d.id, "name": d.name, "name_ar": d.name_ar, "active": d.active} for d in db.scalars(select(Department).order_by(Department.name))]


class Dept(BaseModel):
    name: str
    name_ar: str = ""
    active: bool = True


@router.post("/departments")
def add_dept(b: Dept, db: Session = Depends(get_db), u: User = Depends(require("settings", "admin"))):
    d = Department(**b.model_dump())
    db.add(d)
    db.flush()
    audit.log(db, u, "settings", "create", "department", d.id, f"Department '{d.name}' added", None, b.model_dump())
    db.commit()
    return {"id": d.id}


@router.put("/departments/{did}")
def edit_dept(did: str, b: Dept, db: Session = Depends(get_db), u: User = Depends(require("settings", "admin"))):
    d = db.get(Department, did)
    if not d:
        raise HTTPException(404)
    before = {"name": d.name, "name_ar": d.name_ar, "active": d.active}
    d.name, d.name_ar, d.active = b.name, b.name_ar, b.active
    audit.log(db, u, "settings", "update", "department", d.id, f"Department '{d.name}' edited", before, b.model_dump())
    db.commit()
    return {"ok": True}


# ---- organisation / branding
@router.get("/organisation")
def org(db: Session = Depends(get_db), u: User = Depends(require("settings"))):
    t = db.get(Tenant, "t1")
    return {"name": t.name, "branding": t.branding, "profile": t.profile}


class Org(BaseModel):
    name: str
    branding: dict
    profile: dict = {}


@router.put("/organisation")
def put_org(b: Org, db: Session = Depends(get_db), u: User = Depends(require("settings", "admin"))):
    t = db.get(Tenant, "t1")
    before = {"name": t.name, "branding": t.branding}
    t.name, t.branding, t.profile = b.name, b.branding, b.profile
    audit.log(db, u, "settings", "update", "organisation", "t1", "Hospital profile / branding updated", before, b.model_dump())
    db.commit()
    return {"ok": True}


# ---- configurable records
@router.get("/settings/{key}")
def get_s(key: str, db: Session = Depends(get_db), u: User = Depends(require("dashboard"))):
    if key not in DEFAULTS:
        raise HTTPException(404)
    return {"value": get_setting(db, key)}


class SettingBody(BaseModel):
    value: list | dict


@router.put("/settings/{key}")
def put_s(key: str, b: SettingBody, db: Session = Depends(get_db), u: User = Depends(require("settings", "admin"))):
    if key not in DEFAULTS:
        raise HTTPException(404)
    before = get_setting(db, key)
    put_setting(db, key, b.value)
    audit.log(db, u, "settings", "update", "setting", key, f"Setting '{key}' updated", {"value": before}, {"value": b.value})
    db.commit()
    return {"ok": True}


# ---- users & roles
def user_row(u: User):
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role_id, "role_name": u.role.name,
            "department_ids": u.department_ids, "active": u.active, "invited": u.invited}


@router.get("/users")
def users(db: Session = Depends(get_db), u: User = Depends(require("users"))):
    return [user_row(x) for x in db.scalars(select(User).order_by(User.name))]


@router.get("/roles")
def roles(db: Session = Depends(get_db), u: User = Depends(require("users"))):
    return [{"id": r.id, "name": r.name, "sees_all": r.sees_all, "permissions": r.permissions} for r in db.scalars(select(Role))]


class Invite(BaseModel):
    name: str
    email: EmailStr
    role: str
    department_ids: list[str] = []


@router.post("/users")
def invite(b: Invite, db: Session = Depends(get_db), u: User = Depends(require("users", "create"))):
    if db.scalar(select(User).where(User.email == b.email.lower())):
        raise HTTPException(409, "A user with this email already exists.")
    if not db.get(Role, b.role):
        raise HTTPException(422, "Unknown role")
    nu = User(name=b.name, email=b.email.lower(), role_id=b.role, department_ids=b.department_ids, invited=True, password_hash="")
    db.add(nu)
    db.flush()
    tok = make_token(nu.id, hours=72, kind="reset")
    send_email(db, nu.email, "You're invited to Antier Healthcare Suite",
               f"Hello {nu.name},\n\nYou have been invited. Set your password here:\n{settings.public_web_url}/reset?token={tok}")
    audit.log(db, u, "users", "invite", "user", nu.id, f"Invited {nu.email}", None, b.model_dump())
    db.commit()
    return {"id": nu.id, "invite_link": f"{settings.public_web_url}/reset?token={tok}"}


class UserEdit(BaseModel):
    role: str | None = None
    department_ids: list[str] | None = None
    active: bool | None = None


@router.put("/users/{uid}")
def edit_user(uid: str, b: UserEdit, db: Session = Depends(get_db), u: User = Depends(require("users", "admin"))):
    t = db.get(User, uid)
    if not t:
        raise HTTPException(404)
    if t.id == u.id and b.active is False:
        raise HTTPException(400, "You cannot deactivate your own account.")
    before = user_row(t)
    if b.role:
        t.role_id = b.role
    if b.department_ids is not None:
        t.department_ids = b.department_ids
    if b.active is not None:
        t.active = b.active
    db.flush()
    db.refresh(t)
    audit.log(db, u, "users", "update", "user", t.id, f"User {t.email} updated", before, user_row(t))
    db.commit()
    return user_row(t)

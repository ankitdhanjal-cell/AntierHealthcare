from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import settings
from ..db import get_db
from ..models import User
from ..security import (current_user, decode_token, hash_password, make_token, verify_password)
from ..services import branding, send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User):
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role_id, "role_name": u.role.name,
            "permissions": u.role.permissions, "sees_all": u.role.sees_all, "department_ids": u.department_ids,
            "language": u.language, "timezone": u.timezone}


class Login(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
def login(body: Login, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not u.active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    audit.log(db, u, "auth", "login", "user", u.id, f"{u.name} signed in")
    db.commit()
    return {"token": make_token(u.id), "user": user_out(u)}


@router.get("/me")
def me(u: User = Depends(current_user)):
    return user_out(u)


@router.get("/branding")
def public_branding(db: Session = Depends(get_db)):
    return branding(db) | {"version": settings.app_version}


class Forgot(BaseModel):
    email: EmailStr


@router.post("/forgot")
def forgot(body: Forgot, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if u and u.active:
        tok = make_token(u.id, hours=1, kind="reset")
        send_email(db, u.email, "Reset your password", f"Use this link to set a new password:\n{settings.public_web_url}/reset?token={tok}")
        db.commit()
    return {"ok": True}  # same response either way


class Reset(BaseModel):
    token: str
    password: str


@router.post("/reset")
def reset(body: Reset, db: Session = Depends(get_db)):
    if len(body.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters.")
    u = db.get(User, decode_token(body.token, "reset"))
    if not u:
        raise HTTPException(400, "Invalid link")
    u.password_hash = hash_password(body.password)
    audit.log(db, u, "auth", "password_reset", "user", u.id, "Password reset")
    db.commit()
    return {"ok": True}


class ChangePw(BaseModel):
    current: str
    new: str


@router.post("/change-password")
def change_password(body: ChangePw, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current, u.password_hash):
        raise HTTPException(400, "Current password is incorrect.")
    if len(body.new) < 8:
        raise HTTPException(422, "Password must be at least 8 characters.")
    u.password_hash = hash_password(body.new)
    audit.log(db, u, "auth", "password_change", "user", u.id, "Password changed")
    db.commit()
    return {"ok": True}


class Profile(BaseModel):
    name: str | None = None
    language: str | None = None
    timezone: str | None = None


@router.put("/profile")
def profile(body: Profile, u: User = Depends(current_user), db: Session = Depends(get_db)):
    before = {"name": u.name, "language": u.language, "timezone": u.timezone}
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(u, k, v)
    audit.log(db, u, "auth", "update", "user", u.id, "Profile updated", before, body.model_dump(exclude_none=True))
    db.commit()
    return user_out(u)

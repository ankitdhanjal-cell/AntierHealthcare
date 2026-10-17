from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt(rounds=8)).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False


def make_token(user_id: str, hours: int = 12, kind: str = "access") -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=hours)
    return jwt.encode({"sub": user_id, "exp": exp, "k": kind}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, kind: str = "access") -> str:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired. Please sign in again.")
    if data.get("k") != kind:
        raise HTTPException(401, "Invalid token")
    return data["sub"]


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(401, "Not authenticated")
    user = db.get(User, decode_token(cred.credentials))
    if not user or not user.active:
        raise HTTPException(401, "Account inactive")
    return user


def can(user: User, module: str, action: str = "view") -> bool:
    perms = user.role.permissions.get(module, [])
    return action in perms


def require(module: str, action: str = "view"):
    def dep(user: User = Depends(current_user)) -> User:
        if not can(user, module, action):
            raise HTTPException(403, f"Your role does not allow '{action}' on {module}.")
        return user
    return dep


def dept_scope(user: User):
    """None = all departments; else list of allowed department ids."""
    return None if user.role.sees_all else list(user.department_ids or [])

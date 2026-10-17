from sqlalchemy.orm import Session

from .models import AuditLog, User


def log(db: Session, user: User | None, module: str, action: str, record_type: str = "",
        record_id: str = "", summary: str = "", before=None, after=None):
    db.add(AuditLog(user_id=user.id if user else None, user_name=user.name if user else "System",
                    module=module, action=action, record_type=record_type, record_id=record_id,
                    summary=summary[:400], before=before, after=after))

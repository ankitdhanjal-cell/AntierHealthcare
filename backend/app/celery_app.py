from celery import Celery

from .config import settings

celery = Celery("ahs", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.beat_schedule = {
    "sla-check": {"task": "app.celery_app.sla_task", "schedule": 60.0},
    "send-due-requests": {"task": "app.celery_app.sweep_requests_task", "schedule": 60.0},
}
celery.conf.timezone = "UTC"


@celery.task(name="app.celery_app.sla_task")
def sla_task():
    from .db import SessionLocal
    from .services import check_sla
    with SessionLocal() as db:
        return check_sla(db)


def _send(db, rid):
    from .connectors.sandbox import whatsapp
    from .models import FeedbackRequest, Patient
    r = db.get(FeedbackRequest, rid)
    if r and r.status == "queued":
        whatsapp.send_feedback_request(db, r, db.get(Patient, r.patient_id))
        db.commit()


@celery.task(name="app.celery_app.send_request_task")
def send_request_task(rid: str):
    from .db import SessionLocal
    with SessionLocal() as db:
        _send(db, rid)


@celery.task(name="app.celery_app.sweep_requests_task")
def sweep_requests_task():
    from sqlalchemy import select
    from .db import SessionLocal
    from .models import FeedbackRequest, now
    with SessionLocal() as db:
        for r in db.scalars(select(FeedbackRequest).where(FeedbackRequest.status == "queued", FeedbackRequest.send_at <= now())):
            _send(db, r.id)

"""Sandbox connectors. Each sits behind one interface so a live connector can replace it without UI changes."""
from datetime import timedelta

from sqlalchemy.orm import Session

from .. import audit
from ..config import settings as cfg
from ..models import FeedbackRequest, Patient, User, now
from ..services import branding, get_setting, whatsapp_send


class HISConnector:
    name = "HIS (HL7 v2 / FHIR)"

    def discharge_event(self, db: Session, patient: Patient, send_now: bool, actor: User | None):
        """Receives an ADT^A03-style discharge and queues a feedback request."""
        patient.discharged_at = now()
        delay = 0 if send_now else get_setting(db, "routing").get("feedback_delay_hours", 24)
        req = FeedbackRequest(patient_id=patient.id, department_id=patient.department_id, language=patient.language,
                              send_at=now() + timedelta(hours=delay))
        db.add(req)
        db.flush()
        hl7 = (f"MSH|^~\\&|HIS|HOSPITAL|AHS|SUITE|{now():%Y%m%d%H%M%S}||ADT^A03|{req.id[:8]}|P|2.5\r"
               f"PID|1||{patient.mrn}||{patient.name}\rPV1|1|I")
        audit.log(db, actor, "integrations", "his_discharge", "patient", patient.id,
                  f"Discharge event received for {patient.name}", None, {"request_id": req.id, "send_in_hours": delay})
        return req, hl7


def feedback_message(b: dict, name: str, language: str) -> str:
    """The WhatsApp text a patient receives, in their language."""
    sender = b.get("sender_name", "Antier Healthcare Suite")
    if language == "ar":
        body = (f"مرحباً {name}،\nنشكرك على اختيارك {b['hospital']}. "
                f"يسعدنا أن نسمع رأيك في زيارتك الأخيرة، فهو لا يستغرق سوى دقيقة.")
    else:
        body = (f"Hello {name},\nThank you for choosing {b['hospital']}. "
                f"We'd value your feedback on your recent visit. It takes under a minute.")
    return f"{sender}\n{body}"


def sms_message(b: dict, language: str, link: str) -> str:
    """Short fallback text, kept within one 160-character SMS segment."""
    text = (f"{b['hospital']}: كيف كانت زيارتك؟ رأيك يهمنا (دقيقة): {link}" if language == "ar"
            else f"{b['hospital']}: how was your visit? Tell us in 1 minute: {link}")
    return text if len(text) <= 160 else text.replace(b["hospital"], b["hospital"][:20])


def closing_message(b: dict, name: str, language: str) -> str:
    if language == "ar":
        return (f"مرحباً {name}،\nشكراً لتواصلك معنا. تمت مراجعة ملاحظاتك وإغلاق الموضوع. "
                f"إن بقي لديك أي استفسار فنحن هنا لمساعدتك.\n{b.get('sender_name', b['hospital'])}")
    return (f"Hello {name},\nThank you for speaking with us. We have reviewed your feedback and closed your case. "
            f"If anything is still unresolved, please reply and we will help.\n{b.get('sender_name', b['hospital'])}")


class WhatsAppConnector:
    name = "WhatsApp Business"

    def send_feedback_request(self, db: Session, req: FeedbackRequest, patient: Patient):
        b = branding(db)
        link = f"{cfg.public_web_url}/f/{req.token}"
        whatsapp_send(db, patient, feedback_message(b, patient.name, req.language), req.language, link)
        req.status, req.sent_at = "sent", now()

    def send_closing_message(self, db: Session, patient: Patient, language: str):
        whatsapp_send(db, patient, closing_message(branding(db), patient.name, language), language)


class SMSConnector:
    """Fallback channel: one short text with the same form link."""
    name = "SMS gateway"

    def send_feedback_request(self, db: Session, req: FeedbackRequest, patient: Patient):
        link = f"{cfg.public_web_url}/f/{req.token}"
        whatsapp_send(db, patient, sms_message(branding(db), req.language, link), req.language, link, channel="sms")
        req.status, req.sent_at = "sent", now()


his = HISConnector()
whatsapp = WhatsAppConnector()
sms = SMSConnector()

CARDS = [
    {"key": "his", "name": "HIS (HL7 v2 / FHIR)", "status": "Sandbox", "desc": "Receive ADT discharge events from your hospital information system."},
    {"key": "whatsapp", "name": "WhatsApp Business", "status": "Sandbox", "desc": "Send feedback requests and receive patient enquiries."},
    {"key": "google", "name": "Google Business Profile", "status": "Available", "desc": "Invite satisfied patients to post a public review."},
    {"key": "smtp", "name": "SMTP email", "status": "Available", "desc": "Notification and report email delivery."},
    {"key": "sms", "name": "SMS gateway", "status": "Sandbox", "desc": "Fallback channel for feedback requests when WhatsApp is not available."},
    {"key": "sso", "name": "SSO (SAML / Azure AD)", "status": "Available", "desc": "Single sign-on for hospital staff."},
]

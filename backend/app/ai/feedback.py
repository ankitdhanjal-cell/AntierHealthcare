import re

from ..defaults import THEME_OWNER
from .adapter import OfflineProvider, get_provider, is_arabic, validate

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["sentiment", "score", "themes", "new_themes", "urgency", "translation_en", "summary", "suggested_owner", "staff_mentions"],
    "properties": {
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "score": {"type": "number"},
        "themes": {"type": "array", "items": {"type": "string"}},
        "new_themes": {"type": "array", "items": {"type": "string"}},
        "urgency": {"type": "string", "enum": ["high", "medium", "low"]},
        "translation_en": {"type": "string"},
        "summary": {"type": "string"},
        "suggested_owner": {"type": "string"},
        "staff_mentions": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM = (
    "You analyse hospital patient feedback (English or Arabic) for a quality team. "
    "Return JSON only. Choose themes ONLY from the provided theme list; put any genuinely new theme in new_themes. "
    "suggested_owner must be one of the provided departments. translation_en: English translation of the free text "
    "(or the original if already English; empty string if no text). summary: one short line. urgency: high if safety, "
    "discrimination, or severe distress; medium for clear dissatisfaction; low otherwise. score is -1..1. "
    "staff_mentions: staff members named in the comment, written in English with their title, such as 'Nurse Reem' or 'Dr. Said'; empty if none. "
    "Never give clinical advice."
)

KW = {
    "Billing": ["bill", "billing", "charge", "invoice", "فاتورة", "الفواتير", "فواتير", "رسوم", "محاسب"],
    "Waiting time": ["wait", "long time", "delay", "hours", "انتظار", "الانتظار", "تأخير", "ساعات", "طويل"],
    "Doctor communication": ["doctor", "explain", "طبيب", "الدكتور", "الطبيب", "شرح"],
    "Nursing care": ["nurse", "nursing", "ممرض", "تمريض"],
    "Cleanliness": ["clean", "dirty", "toilet", "نظاف", "وسخ", "نظافة"],
    "Food": ["food", "meal", "طعام", "وجبة", "أكل"],
    "Staff attitude": ["rude", "attitude", "polite", "وقح", "معاملة", "سلوك"],
    "Insurance": ["insurance", "claim", "تأمين"],
    "Discharge process": ["discharge", "خروج", "تخريج"],
    "Facilities": ["parking", "room", "ac ", "غرفة", "مواقف"],
}
NEG = ["bad", "poor", "terrible", "rude", "worst", "angry", "unhappy", "slow", "dirty", "wrong", "سيء", "سيئ", "غاضب", "مستاء", "أسوأ", "تأخير", "طويل", "خطأ"]
POS = ["good", "great", "excellent", "thank", "kind", "friendly", "clean", "happy", "ممتاز", "شكرا", "شكراً", "جيد", "رائع", "لطيف"]


STAFF = re.compile(r"\b(?:Dr\.?|Nurse|Sister|Mr\.?|Ms\.?)\s+[A-Z][a-z]+")


def staff_in(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in STAFF.finditer(text or "")))[:5]


def _offline(rating, text, themes):
    low = (text or "").lower()
    found = [t for t in themes if any(k in low for k in KW.get(t, []))]
    neg = sum(w in low for w in NEG)
    pos = sum(w in low for w in POS)
    score = (rating - 3) / 2 + 0.15 * (pos - neg)
    score = max(-1, min(1, score))
    sentiment = "positive" if score > 0.25 else "negative" if score < -0.25 else "neutral"
    urgency = "high" if (rating <= 1 or sentiment == "negative" and len(found) >= 2) else "medium" if sentiment == "negative" else "low"
    summary = (text or "").strip().split(".")[0][:140] or f"Rated {rating}/5, no comment"
    if is_arabic(text or ""):
        summary = "Arabic comment: " + (", ".join(found) if found else "general feedback")
    return {
        "sentiment": sentiment, "score": round(score, 2), "themes": found[:3], "new_themes": [], "urgency": urgency,
        "translation_en": "" if not text else (text if not is_arabic(text) else "[Translation needs the AI provider key] " + summary),
        "summary": summary, "suggested_owner": THEME_OWNER.get(found[0], "Front office") if found else "Front office",
        "staff_mentions": staff_in(text),
    }


def analyse(rating: int, answers: dict, text: str, themes: list[str], departments: list[str]) -> tuple[dict, str]:
    """Returns (analysis, status). status is 'ok' or 'needs_review'."""
    provider = get_provider()
    try:
        if isinstance(provider, OfflineProvider):
            return _offline(rating, text, themes) | {"provider": "offline"}, "ok"
        user = (f"Rating: {rating}/5\nQuestion scores (1-5): {answers}\nFree text: {text or '(none)'}\n"
                f"Theme list: {themes}\nDepartments: {departments}")
        out = provider.complete_json(SYSTEM, user, SCHEMA)
        if not validate(out, SCHEMA):
            raise ValueError("schema")
        out["themes"] = [t for t in out["themes"] if t in themes]
        out["staff_mentions"] = [s.strip()[:60] for s in out["staff_mentions"] if s.strip()][:5]
        if out["suggested_owner"] not in departments:
            out["suggested_owner"] = "Front office"
        out["provider"] = provider.name
        return out, "ok"
    except Exception:
        return {"sentiment": "neutral", "score": 0, "themes": [], "new_themes": [], "urgency": "medium",
                "translation_en": "", "summary": "Needs review", "suggested_owner": "Front office",
                "staff_mentions": [], "provider": provider.name}, "needs_review"

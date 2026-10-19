"""AI assist for incident reports: suggests category, harm level and a one-line summary from free text."""
from ..defaults import HARM_LEVELS, INCIDENT_CATEGORIES
from .adapter import OfflineProvider, get_provider, validate

CATS = [k for k, _ in INCIDENT_CATEGORIES]
HARMS = [k for k, _ in HARM_LEVELS]
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["category", "harm", "summary"],
    "properties": {
        "category": {"type": "string", "enum": CATS},
        "harm": {"type": "string", "enum": HARMS},
        "summary": {"type": "string"},
    },
}
SYSTEM = (
    "You help a hospital quality team classify patient-safety incident reports written by staff. Return JSON only. "
    "category: the best fit from the allowed list. harm: the actual harm to the patient, where near_miss means the event "
    "was caught before reaching the patient, no_harm reached the patient without harm, then mild, moderate, severe, death. "
    "summary: one factual line under 100 characters with no patient names. Never give clinical advice."
)
KW = {
    "falls": ["fall", "fell", "slipped", "found on the floor", "collapsed"],
    "medication": ["medication", "medicine", "drug", "dose", "tablet", "insulin", "infusion", "prescri", "wrong drug"],
    "patient_identification": ["wrong patient", "wristband", "identification", "name band", "mislabel", "same name", "id band"],
    "pressure_injury": ["pressure injury", "pressure ulcer", "bedsore", "pressure sore", "skin breakdown"],
    "equipment": ["equipment", "pump", "monitor", "ventilator", "defibrillator", "malfunction", "oxygen cylinder", "bed rail", "suction"],
    "infection": ["infection", "mrsa", "isolation", "cannula site", "sepsis", "outbreak", "needle", "contamina"],
}
HARM_KW = [("death", ["died", "death", "passed away"]),
           ("severe", ["fracture", "emergency surgery", "icu transfer", "cardiac arrest", "permanent", "severe"]),
           ("moderate", ["required treatment", "additional treatment", "sutures", "stitches", "extended stay", "admitted for", "moderate"]),
           ("mild", ["bruise", "graze", "minor injury", "mild", "swelling", "small cut"]),
           ("near_miss", ["near miss", "caught before", "picked up before", "noticed before", "almost", "before it reached", "intercepted", "double-check"])]


def _offline(text: str):
    low = text.lower()
    cat = next((c for c, words in KW.items() if any(w in low for w in words)), "other")
    harm = next((h for h, words in HARM_KW if any(w in low for w in words)), "no_harm")
    first = text.strip().split(".")[0].strip()
    return {"category": cat, "harm": harm, "summary": (first[:97] + "...") if len(first) > 100 else first or "Incident report"}


def suggest(text: str) -> tuple[dict, str]:
    """Returns (suggestion, status). status is 'ok' or 'needs_review'."""
    provider = get_provider()
    try:
        if isinstance(provider, OfflineProvider):
            return _offline(text) | {"provider": "offline"}, "ok"
        out = provider.complete_json(SYSTEM, f"Categories: {CATS}\nHarm levels: {HARMS}\nReport: {text}", SCHEMA)
        if not validate(out, SCHEMA):
            raise ValueError("schema")
        return out | {"provider": provider.name}, "ok"
    except Exception:
        return {"category": "other", "harm": "no_harm", "summary": "Needs review", "provider": provider.name}, "needs_review"

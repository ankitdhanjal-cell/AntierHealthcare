"""Default configurable records. Seeded into Settings; editable in the UI."""

THEMES = ["Billing", "Waiting time", "Doctor communication", "Nursing care", "Cleanliness",
          "Food", "Facilities", "Staff attitude", "Discharge process", "Insurance"]

QUESTIONS = [
    {"key": "doctor", "en": "How would you rate the care from your doctor?", "ar": "كيف تقيّم الرعاية التي قدمها لك الطبيب؟", "active": True},
    {"key": "nursing", "en": "How would you rate the nursing care?", "ar": "كيف تقيّم الرعاية التمريضية؟", "active": True},
    {"key": "waiting", "en": "How was your waiting time?", "ar": "كيف كان وقت الانتظار؟", "active": True},
    {"key": "billing", "en": "How clear and fair was billing?", "ar": "ما مدى وضوح وعدالة الفواتير؟", "active": True},
    {"key": "cleanliness", "en": "How clean was the facility?", "ar": "ما مدى نظافة المنشأة؟", "active": True},
]

SLA = {"high": 24, "medium": 72, "low": 168}  # hours

ROUTING = {"min_rating": 4, "required_sentiment": "positive", "feedback_delay_hours": 24,
           "google_review_url": "https://g.page/r/sandbox-review-link",
           "case_below_rating": 5, "mask_patient_names": False}

ESCALATION = {"sla_breach": "quality_manager", "overdue_action": "quality_manager"}

KPIS = [
    {"key": "satisfaction", "name": "Patient satisfaction", "formula": "avg(rating)", "target": 4.0, "amber": 3.8, "direction": "higher"},
    {"key": "closure_time", "name": "Average complaint closure time (h)", "formula": "avg(closed_at - created_at)", "target": 72, "amber": 96, "direction": "lower"},
    {"key": "cases_past_sla", "name": "Cases past SLA", "formula": "count(open and due_at < now)", "target": 3, "amber": 6, "direction": "lower"},
]

MOD = ["feedback", "cases", "settings", "users", "audit", "integrations", "dashboard"]


def perms(**kw):
    return {m: kw.get(m, []) for m in MOD}


V, C, A, X = "view", "create", "approve", "admin"
ROLES = [
    ("quality_manager", "Quality Manager", True, perms(feedback=[V, C, A], cases=[V, C, A], dashboard=[V], audit=[V], integrations=[V, C], settings=[V], users=[V])),
    ("patient_relations", "Patient Relations Officer", True, perms(feedback=[V, C, A], cases=[V, C, A], dashboard=[V])),
    ("department_head", "Department Head", False, perms(feedback=[V], cases=[V, C], dashboard=[V])),
    ("infection_control", "Infection Control Nurse", False, perms(feedback=[V], cases=[V], dashboard=[V])),
    ("staff_reporter", "Staff reporter", False, perms(cases=[V])),
    ("front_desk", "Front desk", False, perms(feedback=[V], cases=[V], dashboard=[V])),
    ("management_viewer", "Management viewer", True, perms(feedback=[V], cases=[V], dashboard=[V], audit=[V])),
    ("admin", "Admin", True, perms(feedback=[V], cases=[V], dashboard=[V], audit=[V, X], integrations=[V, C, X], settings=[V, C, A, X], users=[V, C, A, X])),
]

DEPARTMENTS = [("OPD", "العيادات الخارجية"), ("Emergency", "الطوارئ"), ("Inpatient wards", "الأجنحة الداخلية"),
               ("ICU", "العناية المركزة"), ("Maternity", "الولادة"), ("Paediatrics", "طب الأطفال"),
               ("Radiology", "الأشعة"), ("Laboratory", "المختبر"), ("Billing and insurance", "الفواتير والتأمين"),
               ("Front office", "المكتب الأمامي")]

# theme -> department that normally owns it
THEME_OWNER = {"Billing": "Billing and insurance", "Insurance": "Billing and insurance", "Waiting time": "OPD",
               "Doctor communication": "OPD", "Nursing care": "Inpatient wards", "Cleanliness": "Inpatient wards",
               "Food": "Inpatient wards", "Facilities": "Front office", "Staff attitude": "Front office",
               "Discharge process": "Inpatient wards"}

DEFAULTS_FOR_SEED = {"themes": THEMES, "questions": QUESTIONS, "sla": SLA, "routing": ROUTING, "escalation": ESCALATION, "kpis": KPIS}

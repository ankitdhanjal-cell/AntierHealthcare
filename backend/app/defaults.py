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
    {"key": "satisfaction", "name": "Patient satisfaction", "formula": "Average of the overall star ratings", "target": 4.0, "amber": 3.8, "direction": "higher"},
    {"key": "closure_time", "name": "Average complaint closure time (hours)", "formula": "Average time from case opened to case closed", "target": 72, "amber": 96, "direction": "lower"},
    {"key": "cases_past_sla", "name": "Cases past SLA", "formula": "Open cases whose due time has passed", "target": 3, "amber": 6, "direction": "lower"},
]

MOD = ["feedback", "cases", "settings", "users", "audit", "integrations", "dashboard", "incidents", "accreditation", "audits", "indicators", "reports"]


def perms(**kw):
    return {m: kw.get(m, []) for m in MOD}


V, C, A, X = "view", "create", "approve", "admin"
ROLES = [
    ("quality_manager", "Quality Manager", True, perms(feedback=[V, C, A], cases=[V, C, A], dashboard=[V], audit=[V], integrations=[V, C], settings=[V], users=[V], incidents=[V, C, A], accreditation=[V, C, A], audits=[V, C, A, X], indicators=[V, C, A, X], reports=[V, C])),
    ("patient_relations", "Patient Relations Officer", True, perms(feedback=[V, C, A], cases=[V, C, A], dashboard=[V], incidents=[V, C], indicators=[V])),
    ("department_head", "Department Head", False, perms(feedback=[V], cases=[V, C], dashboard=[V], incidents=[V, C], accreditation=[V], audits=[V, C], indicators=[V])),
    ("nurse_manager", "Ward Nurse Manager", False, perms(feedback=[V], cases=[V, C], dashboard=[V], incidents=[V, C], audits=[V, C], accreditation=[V], indicators=[V])),
    ("infection_control", "Infection Control Nurse", False, perms(feedback=[V], cases=[V], dashboard=[V], incidents=[V, C], accreditation=[V, C], audits=[V, C, A, X], indicators=[V, C])),
    ("staff_reporter", "Staff reporter", False, perms(incidents=[V, C])),
    ("front_desk", "Front desk", False, perms(feedback=[V], cases=[V], dashboard=[V], incidents=[C])),
    ("management_viewer", "Management viewer", True, perms(feedback=[V], cases=[V], dashboard=[V], audit=[V], incidents=[V], accreditation=[V], audits=[V], indicators=[V], reports=[V])),
    ("admin", "Admin", True, perms(feedback=[V, C, A], cases=[V, C, A], dashboard=[V], audit=[V, X], integrations=[V, C, X], settings=[V, C, A, X], users=[V, C, A, X], incidents=[V, C, A, X], accreditation=[V, C, A, X], audits=[V, C, A, X], indicators=[V, C, A, X], reports=[V, C, X])),
]

DEPARTMENTS = [("OPD", "العيادات الخارجية"), ("Emergency", "الطوارئ"), ("Inpatient wards", "الأجنحة الداخلية"),
               ("ICU", "العناية المركزة"), ("Maternity", "الولادة"), ("Paediatrics", "طب الأطفال"),
               ("Radiology", "الأشعة"), ("Laboratory", "المختبر"), ("Billing and insurance", "الفواتير والتأمين"),
               ("Front office", "المكتب الأمامي"),
               ("Operating Theatre", "غرفة العمليات")]

# theme -> department that normally owns it
THEME_OWNER = {"Billing": "Billing and insurance", "Insurance": "Billing and insurance", "Waiting time": "OPD",
               "Doctor communication": "OPD", "Nursing care": "Inpatient wards", "Cleanliness": "Inpatient wards",
               "Food": "Inpatient wards", "Facilities": "Front office", "Staff attitude": "Front office",
               "Discharge process": "Inpatient wards"}

DEFAULTS_FOR_SEED = {"themes": THEMES, "questions": QUESTIONS, "sla": SLA, "routing": ROUTING, "escalation": ESCALATION, "kpis": KPIS}


# ---- incidents
INCIDENT_CATEGORIES = [("falls", "Falls"), ("medication", "Medication error"), ("patient_identification", "Patient identification"),
                       ("pressure_injury", "Pressure injury"), ("equipment", "Equipment"), ("infection", "Infection"), ("other", "Other")]
HARM_LEVELS = [("near_miss", "Near miss"), ("no_harm", "No harm"), ("mild", "Mild"), ("moderate", "Moderate"), ("severe", "Severe"), ("death", "Death")]
INCIDENT_STATUSES = ["Reported", "Triaged", "Under investigation", "Actions open", "Closed"]
FACTOR_GROUPS = [("people", "People"), ("process", "Process"), ("equipment", "Equipment"), ("environment", "Environment"),
                 ("communication", "Communication"), ("policy", "Policy")]
# hours to complete the investigation, by harm level. Severe and death are sentinel events with the strictest deadline.
INCIDENT_SLA = {"near_miss": 504, "no_harm": 504, "mild": 336, "moderate": 240, "severe": 72, "death": 72}
SENTINEL_HARM = ("severe", "death")
DEFAULTS_FOR_SEED["incident_sla"] = INCIDENT_SLA

# ---- accreditation and quality actions
ELEMENT_STATUSES = ["Met", "Partially met", "Not met", "Not applicable"]
ACCREDITATION = {"name": "National Accreditation Survey", "survey_date": ""}
DEFAULTS_FOR_SEED["accreditation"] = ACCREDITATION

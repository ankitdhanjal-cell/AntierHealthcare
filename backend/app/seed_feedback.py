"""Patients, feedback, review requests and cases for the sandbox.

Texts come from seed_data/feedback_texts.json. Every text is used at most once, so no sentence repeats in the data.
All times are generated in the hospital timezone (Asia/Muscat) and stored as UTC.
"""
import json
import random
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

from . import defaults as D
from .connectors.sandbox import closing_message, feedback_message, sms_message
from .services import branding
from .config import settings as cfg
from .models import (AuditLog, Case, CaseCall, CaseEvent, FeedbackChannel, FeedbackRequest, FeedbackResponse, Message, Patient, now)

TZ = ZoneInfo("Asia/Muscat")
TEXTS = json.loads((Path(__file__).parent / "seed_data" / "feedback_texts.json").read_text(encoding="utf-8"))
Q_KEYS = [q["key"] for q in D.QUESTIONS]

# attending doctors per department (fictional)
DOCTORS = {"OPD": ["Dr. Salim Al-Rawahi", "Dr. Anjali Verma", "Dr. Peter Collins"], "Emergency": ["Dr. Hamdan Al-Lawati", "Dr. Ravi Menon", "Dr. Kate Sullivan"],
           "Inpatient wards": ["Dr. Zainab Al-Balushi", "Dr. Mathew George", "Dr. Alan Frost"], "ICU": ["Dr. Majid Al-Hosni", "Dr. Sunita Rao"],
           "Maternity": ["Dr. Meera Nair", "Dr. Laila Al-Kharusi", "Dr. Helen Marsh"], "Paediatrics": ["Dr. Priya Raman", "Dr. Omar Al-Saadi"],
           "Radiology": ["Dr. Imran Qureshi", "Dr. Fiona Hart"], "Laboratory": ["Dr. Nasser Al-Siyabi"], "Billing and insurance": ["Dr. Khalid Al-Wahaibi"],
           "Front office": ["Dr. Rashid Al-Harthy"]}
DEPT_WEIGHTS = {"OPD": 30, "Emergency": 22, "Inpatient wards": 15, "ICU": 3, "Maternity": 8, "Paediatrics": 8, "Radiology": 5,
                "Laboratory": 4, "Billing and insurance": 3, "Front office": 2}
# local-hour weights: busiest mid-morning and early evening
HOUR_W = [0.3, 0.2, 0.2, 0.2, 0.3, 0.6, 1.2, 2.5, 4, 5, 5.5, 5, 4, 3.5, 3.5, 4, 4.5, 4.5, 3.5, 2.5, 1.8, 1.2, 0.8, 0.5]
WEEKDAY_W = [1.0, 1.0, 0.95, 1.0, 0.55, 0.8, 1.1]  # Mon..Sun (Fri lighter, Sat/Sun busy in Oman)

ACTIONS = {
    "Waiting time": ["Clinic start times reviewed with the department head.", "Triage staffing for peak hours adjusted.", "Queue tokens introduced at the affected counter.",
                     "Reminder issued to clinics to post delay notices.", "Appointment slots re-spaced for the affected session."],
    "Billing": ["Billing supervisor corrected the invoice.", "Charges re-checked against the signed estimate and adjusted.", "Cashier team briefed on explaining line items.",
                "Refund raised and approved by finance.", "Itemised bill re-issued with plain-language descriptions."],
    "Doctor communication": ["Raised with the consultant in the quality huddle.", "Doctor met the family to go through the plan.", "Shared as learning at the medical staff meeting.",
                             "Follow-up consultation arranged."],
    "Nursing care": ["Discussed with the ward nurse manager.", "Round checklist refreshed on the ward.", "Staffing for the shift reviewed.", "Nurse coaching completed."],
    "Cleanliness": ["Housekeeping supervisor inspected the area.", "Cleaning schedule increased for this location.", "Deep clean completed the same day."],
    "Food": ["Dietitian reviewed the menu entry.", "Catering team briefed on meal timing.", "Allergy flag process re-checked with catering."],
    "Facilities": ["Engineering raised a repair job.", "Facilities lead reviewed the issue.", "Security and facilities agreed an interim arrangement."],
    "Staff attitude": ["Manager held a conversation with the staff member.", "Customer-care refresher scheduled for the team.", "Apology issued by the department head."],
    "Discharge process": ["Discharge checklist reinforced with the ward.", "Pharmacy and ward agreed an earlier medicine preparation.", "Discharge coordinator informed."],
    "Insurance": ["Insurance desk liaised with the insurer.", "Approval re-submitted and confirmed.", "Insurance team briefed on the correct process."],
}
CALL_OUTCOMES = [("reached", "Patient reached"), ("apologised", "Apologised to patient"), ("resolved", "Resolved on the call"),
                 ("follow_up", "Follow-up needed"), ("no_answer", "No answer")]
CALL_WEIGHTS = [30, 30, 25, 8, 7]  # most call-backs reach the patient; a few leave the loop open
ARABIC_STAFF = {"الدكتورة سلمى": "Dr. Salma", "مبارك": "Mubarak (security)", "نورة": "Nurse Noura", "الدكتور عادل": "Dr. Adil", "ريم": "Nurse Reem", "د. سالم": "Dr. Salim", "منى": "Mona (physiotherapy)", "خالد": "Khalid (security)", "الدكتورة هدى": "Dr. Huda", "سعيد": "Saeed (accounts)",
                "الممرضة أمل": "Nurse Amal", "الدكتور ناصر": "Dr. Nasser", "فاطمة": "Fatima (reception)"}
WARD_BY_DEPT = {"Inpatient wards": ["Ward 2", "Ward 3", "Ward 4"], "ICU": ["ICU"], "Maternity": ["Maternity ward"], "Paediatrics": ["Paediatric ward"]}
CHANNELS = [("Ward 2 visitors' lounge", "ward", "Inpatient wards"), ("Ward 3 corridor", "ward", "Inpatient wards"), ("Ward 4 nurses' station", "ward", "Inpatient wards"),
            ("ICU family waiting room", "ward", "ICU"), ("Maternity ward", "ward", "Maternity"), ("OPD reception", "clinic", "OPD"), ("Emergency waiting area", "clinic", "Emergency"),
            ("Paediatric clinic", "clinic", "Paediatrics"), ("Radiology reception", "clinic", "Radiology")]


def _local_dt(rnd: random.Random, age_days: int, used: set, max_dt: datetime):
    """Random local timestamp `age_days` ago; hour/weekday weighted; unique to the second."""
    base = (datetime.now(TZ) - timedelta(days=age_days)).date()
    for _ in range(50):
        hour = rnd.choices(range(24), HOUR_W)[0]
        dt = datetime.combine(base, time(hour, rnd.randint(0, 59), rnd.randint(0, 59)), TZ)
        if dt <= max_dt and dt not in used:
            used.add(dt)
            return dt.astimezone(ZoneInfo("UTC"))
    dt = max_dt - timedelta(seconds=len(used))
    used.add(dt)
    return dt.astimezone(ZoneInfo("UTC"))


STAFF_NAMES = {"Priya Menon", "Layla Al-Harthy", "Omar Al-Balushi", "Nadia Fernandes", "Khalid Al-Siyabi", "Fatma Al-Lawati", "Hessa Al-Mamari", "Maryam Al-Kharusi", "Vikram Pillai"}
AR_FIRST = ["Mohammed", "Ahmed", "Fatima", "Aisha", "Khalid", "Salma", "Yusuf", "Mariam", "Hamad", "Noor", "Rashid", "Huda", "Said", "Zahra", "Badar", "Amna", "Faisal", "Shamsa"]
AR_LAST = ["Al-Habsi", "Al-Kindi", "Al-Farsi", "Al-Mamari", "Al-Zadjali", "Al-Hinai", "Al-Amri", "Al-Busaidi", "Al-Shukaili", "Al-Maskari", "Al-Rashdi"]
EN_FIRST = ["Arjun", "Priya", "Rahul", "Ananya", "Imran", "Sana", "Vikram", "Deepa", "James", "Emily", "Oliver", "Sophie", "Daniel", "Hannah", "Suresh", "Lakshmi", "Thomas", "Clara", "Matthew", "Isabel"]
EN_LAST = ["Khan", "Sharma", "Nair", "Patel", "Iqbal", "Thomas", "Walker", "Brown", "Hughes", "Rao", "Menon", "Clarke", "Pillai", "Siddiqui", "Fernandes", "Reid", "Bennett"]


def _patient_name(rnd, arabic: bool) -> str:
    """Arabic-speaking patients get Arabic names and the rest English or South Asian ones; never a staff member's name."""
    while True:
        n = f"{rnd.choice(AR_FIRST)} {rnd.choice(AR_LAST)}" if arabic else f"{rnd.choice(EN_FIRST)} {rnd.choice(EN_LAST)}"
        if n not in STAFF_NAMES:
            return n


def generate(db, rnd: random.Random, dep: dict, users: dict):
    used: set = set()
    now_local = datetime.now(TZ)
    brand = branding(db)
    dep_name = {d.id: n for n, d in dep.items()}
    channels = {}
    for name, kind, dname in CHANNELS:  # printable QR codes for wards and clinics
        ch = FeedbackChannel(name=name, kind=kind, department_id=dep[dname].id)
        db.add(ch)
        channels.setdefault(dname, ch)
    db.flush()
    dept_names = list(DEPT_WEIGHTS)

    # ---------- patients
    patients = []
    for i in range(700):
        arabic = rnd.random() < 0.40
        dname = rnd.choices(dept_names, [DEPT_WEIGHTS[n] for n in dept_names])[0]
        discharged = now() - timedelta(days=rnd.randint(1, 180))
        wards = WARD_BY_DEPT.get(dname)
        los = rnd.randint(3, 14) if dname == "ICU" else rnd.randint(2, 9) if wards else 0
        p = Patient(mrn=f"MRN{100000 + i}", name=_patient_name(rnd, arabic), phone=f"+968 9{rnd.randint(1000000, 9999999)}",
                    language="ar" if arabic else "en", department_id=dep[dname].id, attending=rnd.choice(DOCTORS[dname]), discharged_at=discharged,
                    admitted_at=discharged - timedelta(days=los) if wards else None, ward=f"{rnd.choice(wards)}, bed {rnd.randint(1, 24)}" if wards else "")
        patients.append(p)
    db.add_all(patients)
    db.flush()
    by_lang_dept = {}
    for p in patients:
        by_lang_dept.setdefault((p.language, p.department_id), []).append(p)

    # ---------- event skeletons: month index 5 = current month. Month 3 is the bad one (waiting time), 4-5 improve.
    N = 820
    events = []
    for i in range(N):
        age = rnd.randint(0, 179)
        month = 5 - age // 30
        neg = 0.15 + (0.20 if month == 3 else 0) - (0.05 if month >= 4 else 0)
        r = rnd.random()
        events.append({"age": age, "month": month, "sentiment": "negative" if r < neg else "neutral" if r < neg + 0.18 else "positive"})
    # guarantee a handful of fresh negatives so there are open cases inside SLA
    fresh = [e for e in events if e["age"] <= 2]
    for e in fresh[:9]:
        e["sentiment"] = "negative"

    # ---------- assign texts, each used once. Negatives first, then neutrals, then compliments.
    comp_en, comp_ar = list(TEXTS["complaints_en"]), list(TEXTS["complaints_ar"])
    pos_en, pos_ar = list(TEXTS["compliments_en"]), list(TEXTS["compliments_ar"])
    for pool in (comp_en, comp_ar, pos_en, pos_ar):
        rnd.shuffle(pool)

    def take_complaint(month):
        arabic = rnd.random() < 0.26 and comp_ar
        pool = comp_ar if arabic else comp_en
        if not pool:
            pool = comp_en or comp_ar
        if not pool:
            return None
        if month == 3 and rnd.random() < 0.6:
            for i, row in enumerate(pool):
                if row[0] == "Waiting time":
                    return pool.pop(i), pool is comp_ar
        return pool.pop(), pool is comp_ar

    def take_compliment():
        arabic = rnd.random() < 0.26 and pos_ar
        pool = pos_ar if arabic else pos_en
        if not pool:
            return None
        return pool.pop(), pool is pos_ar

    for e in sorted(events, key=lambda e: e["sentiment"] != "negative"):  # negatives first
        e["text"] = None
        if e["sentiment"] == "negative":
            e["text"] = take_complaint(e["month"])
        elif e["sentiment"] == "neutral" and rnd.random() < 0.40:
            e["text"] = take_complaint(e["month"])
        elif e["sentiment"] == "positive" and rnd.random() < 0.13:
            e["text"] = take_compliment()
    # a negative with no text left cannot get a meaningful case; downgrade to neutral without text
    for e in events:
        if e["sentiment"] == "negative" and not e["text"]:
            e["sentiment"] = "neutral"

    # ---------- feedback responses
    case_candidates = []
    for e in sorted(events, key=lambda e: -e["age"]):
        sentiment, rating = e["sentiment"], None
        rating = {"negative": rnd.choice([1, 1, 2, 2, 2]), "neutral": 3, "positive": rnd.choice([4, 5, 5, 5])}[sentiment]
        text_, trans, themes, summary, lang, staff = "", "", [], "", None, []
        if e["text"]:
            row, is_ar = e["text"]
            lang = "ar" if is_ar else "en"
            if sentiment == "positive":
                if row[0]:
                    staff = [ARABIC_STAFF.get(row[0], row[0])] if is_ar else [row[0] if row[0].startswith(("Dr.", "Nurse", "Sister")) else row[0]]
                text_ = row[1]
                trans, summary = (row[2], row[3]) if is_ar else (row[1], row[2])
            else:
                themes = [row[0]]
                text_ = row[1]
                trans, summary = (row[2], row[3]) if is_ar else (row[1], row[2])
        pool = by_lang_dept
        dname = rnd.choices(dept_names, [DEPT_WEIGHTS[n] for n in dept_names])[0]
        if themes:  # complaint lands in a department that plausibly owns the theme most of the time
            owner = D.THEME_OWNER.get(themes[0], "Front office")
            dname = owner if rnd.random() < 0.55 else dname
        plang = lang or ("ar" if rnd.random() < 0.4 else "en")
        cands = pool.get((plang, dep[dname].id)) or [p for p in patients if p.language == plang]
        p = rnd.choice(cands)
        urgency = "high" if rating == 1 else "medium" if sentiment == "negative" else "low"
        owner_dept = D.THEME_OWNER.get(themes[0], "Front office") if themes else "Front office"
        created = _local_dt(rnd, e["age"], used, now_local)
        ai = {"sentiment": sentiment, "score": {"negative": -0.6, "neutral": 0.0, "positive": 0.7}[sentiment], "themes": themes, "new_themes": [],
              "urgency": urgency, "translation_en": trans, "summary": summary or f"Rated {rating}/5, no comment",
              "suggested_owner": owner_dept, "staff_mentions": staff, "provider": "precomputed"}
        nps = {5: rnd.choice([10, 10, 10, 9, 9, 8]), 4: rnd.choice([9, 9, 8, 8, 7, 7]), 3: rnd.choice([5, 6, 7, 7, 8]), 2: rnd.choice([2, 3, 4, 5]), 1: rnd.choice([0, 0, 1, 2, 3])}[rating]
        chan = rnd.choices(["whatsapp", "sms"], [88, 12])[0]
        req = FeedbackRequest(patient_id=p.id, department_id=p.department_id, status="answered", language=plang, created_at=created - timedelta(hours=rnd.randint(2, 30)),
                              send_at=created - timedelta(hours=rnd.randint(2, 30)), google_invited=(rating >= 4 and sentiment == "positive"), channel=chan)
        req.sent_at = req.send_at
        walk_in = channels.get(dep_name[p.department_id]) if rnd.random() < 0.10 else None
        if walk_in:  # this response came from the ward or clinic QR code
            req.channel, req.channel_id, req.sent_at = "qr", walk_in.id, None
        req.google_clicked = req.google_invited and rnd.random() < 0.38
        db.add(req)
        db.flush()
        fb = FeedbackResponse(request_id=req.id, patient_id=p.id, department_id=p.department_id, rating=rating,
                              answers={k: min(5, max(1, rating + rnd.randint(-1, 1))) for k in Q_KEYS}, text=text_, language=plang, created_at=created,
                              ai=ai, sentiment=sentiment, themes=themes, urgency=urgency, reviewed=e["age"] > 14, nps=nps, attending=p.attending, staff_mentions=staff, channel_id=req.channel_id)
        db.add(fb)
        if sentiment == "negative":
            case_candidates.append((fb, owner_dept, themes[0] if themes else ""))
    db.flush()

    # requests that never got an answer (response rates are well under 100 percent), plus the last few messages sent
    sent_recent = []
    for _ in range(1350):
        pt = rnd.choice(patients)
        t_sent = _local_dt(rnd, rnd.randint(0, 179), used, now_local)
        chan = rnd.choices(["whatsapp", "sms"], [88, 12])[0]
        r = FeedbackRequest(patient_id=pt.id, department_id=pt.department_id, status="sent", language=pt.language, created_at=t_sent - timedelta(hours=2), send_at=t_sent, sent_at=t_sent, channel=chan)
        db.add(r)
        sent_recent.append((t_sent, pt, r))
    for t_sent, pt, r in sorted(sent_recent, key=lambda x: x[0])[-24:]:
        link = f"{cfg.public_web_url}/f/{r.token}"
        body = sms_message(brand, pt.language, link) if r.channel == "sms" else feedback_message(brand, pt.name, pt.language)
        db.add(Message(patient_id=pt.id, direction="out", body=body, language=pt.language, channel=r.channel, link=link, created_at=t_sent))
    db.flush()

    # ---------- cases: one per negative response. Recent ones stay open; 6 older ones are unresolved and past SLA; the rest are closed.
    pro = users["patient_relations"]
    head_for = {}  # department id -> its head or nurse manager
    for role in ("department_head", "nurse_manager"):
        for did in users[role].department_ids or []:
            head_for.setdefault(did, users[role])
    case_candidates.sort(key=lambda x: x[0].created_at)
    sla = D.SLA
    stale_ids = set()
    stale_pool = [c for c in case_candidates if timedelta(days=3) < now() - c[0].created_at < timedelta(days=30)]
    for c in rnd.sample(stale_pool, min(6, len(stale_pool))):
        stale_ids.add(c[0].id)
    audit_rows = []
    for n, (fb, owner_dept, theme) in enumerate(case_candidates, 1):
        due = fb.created_at + timedelta(hours=sla[fb.urgency])
        still_open = due > now() or fb.id in stale_ids
        owner = head_for.get(fb.department_id, pro)
        overdue = still_open and due < now()
        status = (rnd.choice(["Assigned", "In investigation"])) if still_open else rnd.choice(["Resolved", "Closed", "Closed"])
        c = Case(number=f"CS-{1000 + n}", feedback_id=fb.id, patient_id=fb.patient_id, department_id=fb.department_id, title=fb.ai["summary"][:300],
                 urgency=fb.urgency, status=status, owner_id=owner.id, due_at=due, created_at=fb.created_at, breach_notified=overdue)
        patient_first = db.get(Patient, fb.patient_id).name.split()[0]
        if not still_open:
            month = 5 - (now() - fb.created_at).days // 30
            factor = 1.7 if month == 3 else 0.7 if month >= 4 else 1.0  # bad month closes slowly, improvement faster
            hours = max(6, int(sla[fb.urgency] * rnd.uniform(0.35, 1.25) * factor))
            c.closed_at = min(fb.created_at + timedelta(hours=hours), now() - timedelta(minutes=30))
            action = rnd.choice(ACTIONS.get(theme, ACTIONS["Staff attitude"]))
            outcome_key, outcome_text = rnd.choices(CALL_OUTCOMES, CALL_WEIGHTS)[0]
            c.resolution = f"{action} Called {patient_first} on {c.closed_at.astimezone(TZ):%d %b %Y}: {outcome_text.lower()}."
        db.add(c)
        db.flush()
        fb.case_id = c.id
        t0 = fb.created_at
        db.add(CaseEvent(case_id=c.id, kind="created", text=f"Case opened from feedback (rating {fb.rating}/5)", created_at=t0))
        audit_rows.append(AuditLog(at=t0, user_name="System", module="cases", action="create", record_type="case", record_id=c.id,
                                   summary=f"Case {c.number} opened", after={"urgency": fb.urgency, "due_at": due.isoformat()}))
        if c.owner_id:
            db.add(CaseEvent(case_id=c.id, kind="assigned", text=f"Assigned to {owner.name}", actor="System", created_at=t0 + timedelta(minutes=rnd.randint(2, 25))))
        if overdue or (not still_open and c.closed_at and c.closed_at > due):
            db.add(CaseEvent(case_id=c.id, kind="escalated", text="SLA breached; escalated to Quality Manager", created_at=due))
        if c.closed_at:
            call_at = c.closed_at - timedelta(minutes=rnd.randint(20, 240))
            db.add(CaseCall(case_id=c.id, outcome=outcome_key, note="", actor=owner.name, created_at=call_at))
            db.add(CaseEvent(case_id=c.id, kind="call", text=f"Called patient: {outcome_text}", actor=owner.name, created_at=call_at))
            db.add(CaseEvent(case_id=c.id, kind="closed", text=f"Closed: {c.resolution}", actor=owner.name, created_at=c.closed_at))
            if outcome_key in ("reached", "apologised", "resolved") and rnd.random() < 0.35:  # optional closing message to the patient
                pt = db.get(Patient, fb.patient_id)
                c.closing_message_at = c.closed_at + timedelta(minutes=rnd.randint(5, 90))
                db.add(Message(patient_id=pt.id, direction="out", body=closing_message(brand, pt.name, pt.language), language=pt.language, channel="whatsapp", created_at=c.closing_message_at))
                db.add(CaseEvent(case_id=c.id, kind="note", text="Closing message sent to the patient", actor=owner.name, created_at=c.closing_message_at))
            audit_rows.append(AuditLog(at=c.closed_at, user_id=owner.id, user_name=owner.name, module="cases", action="status", record_type="case",
                                       record_id=c.id, summary=f"{c.number} → {status}", before={"status": "Assigned"}, after={"status": status}))
    db.add_all(audit_rows)

"""Rebuilds the sandbox from scratch:  python -m app.seed   (add --if-empty to skip when data exists)."""
import random
import uuid
import sys
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import defaults as D
from .db import Base, SessionLocal, engine
from .models import (Case, CaseEvent, Department, FeedbackResponse, Patient, Role, Setting, Site, Tenant, User, now)
from .security import hash_password

PASSWORD = "Sandbox@2026"
USERS = [
    ("Layla Al-Harthy", "quality.manager@hospital.example", "quality_manager", []),
    ("Omar Al-Balushi", "patient.relations@hospital.example", "patient_relations", []),
    ("Dr. Salim Al-Rawahi", "dept.head@hospital.example", "department_head", ["OPD", "Emergency"]),
    ("Nadia Fernandes", "infection.control@hospital.example", "infection_control", ["Inpatient wards", "ICU"]),
    ("Priya Menon", "staff@hospital.example", "staff_reporter", ["Inpatient wards"]),
    ("Khalid Al-Siyabi", "front.desk@hospital.example", "front_desk", ["Front office"]),
    ("Fatma Al-Lawati", "management@hospital.example", "management_viewer", []),
    ("Admin User", "admin@hospital.example", "admin", []),
]
FIRST = ["Mohammed", "Ahmed", "Fatima", "Aisha", "Khalid", "Salma", "Yusuf", "Mariam", "Hamad", "Noor", "Rashid", "Huda",
         "Arjun", "Priya", "Rahul", "Ananya", "Imran", "Sana", "Vikram", "Deepa", "James", "Emily", "Oliver", "Sophie", "Daniel", "Hannah"]
LAST = ["Al-Habsi", "Al-Kindi", "Al-Farsi", "Al-Mamari", "Al-Zadjali", "Al-Hinai", "Khan", "Sharma", "Nair", "Patel", "Iqbal",
        "Thomas", "Walker", "Brown", "Hughes", "Al-Amri", "Al-Busaidi", "Rao", "Menon", "Clarke"]

# (rating band, theme(s), english, arabic, english-translation-of-arabic, summary)
NEG_EN = {
    "Billing": ["The final bill had charges I did not understand and nobody could explain them.", "I was billed twice for the same service and it took days to correct."],
    "Waiting time": ["I waited over two hours in OPD before seeing the doctor.", "The waiting time for my discharge papers was far too long."],
    "Cleanliness": ["The room and bathroom were not clean when I was admitted."],
    "Staff attitude": ["The front desk staff were dismissive when I asked a question."],
    "Doctor communication": ["The doctor did not take time to explain the plan to my family."],
    "Food": ["Meals arrived cold and late."],
}
NEG_AR = {
    "Billing": [("الفاتورة كانت غير واضحة وفيها رسوم لم يشرحها لي أحد.", "The bill was unclear and had charges nobody explained to me.")],
    "Waiting time": [("انتظرت أكثر من ساعتين قبل أن يراني الطبيب.", "I waited more than two hours before the doctor saw me.")],
    "Billing+Waiting time": [("انتظار طويل جداً وفاتورة غير واضحة، تجربة سيئة.", "Very long wait and an unclear bill, a poor experience.")],
}
POS_EN = ["Excellent care, the nurses were kind and attentive.", "Very professional doctor, thank you.", "Smooth discharge and friendly staff.", "Clean facility and quick service."]
POS_AR = [("شكراً لكم، الرعاية كانت ممتازة والطاقم لطيف.", "Thank you, the care was excellent and the staff kind.")]
Q_KEYS = [q["key"] for q in D.QUESTIONS]


def rebuild(db: Session):
    db.rollback()
    db.close()
    rnd = random.Random(2026)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db.expire_all()
    try:  # pgvector is only needed for the Assistant module; optional locally
        with engine.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        pass
    db.add(Tenant(id="t1", name="Demo Hospital", branding={"primary_color": "#0f766e", "sender_name": "Antier Healthcare Suite", "logo_url": ""},
                  profile={"beds": 120, "type": "Private hospital", "deployment_note": "Runs on the hospital's own server or an approved cloud region."}))
    db.add(Site(id="s1", tenant_id="t1", name="Main campus"))
    for k, v in D.DEFAULTS_FOR_SEED.items():
        db.add(Setting(tenant_id="t1", key=k, value=v))
    for rid, name, sees_all, perms in D.ROLES:
        db.add(Role(id=rid, name=name, sees_all=sees_all, permissions=perms))
    dep = {}
    for n, ar in D.DEPARTMENTS:
        d = Department(name=n, name_ar=ar)
        db.add(d)
        dep[n] = d
    db.flush()
    pw = hash_password(PASSWORD)
    users = {}
    for name, email, role, depts in USERS:
        u = User(id=uuid.uuid5(uuid.NAMESPACE_DNS, email).hex, name=name, email=email, role_id=role, department_ids=[dep[x].id for x in depts], password_hash=pw)
        db.add(u)
        users[role] = u
    db.flush()

    patients = []
    for i in range(600):
        f, l = rnd.choice(FIRST), rnd.choice(LAST)
        arabic = rnd.random() < 0.4
        p = Patient(mrn=f"MRN{100000 + i}", name=f"{f} {l}", phone=f"+968 9{rnd.randint(1000000, 9999999)}",
                    language="ar" if arabic else "en", department_id=rnd.choice(list(dep.values())[:6]).id,
                    attending=f"Dr. {rnd.choice(LAST)}", discharged_at=now() - timedelta(days=rnd.randint(1, 180)))
        patients.append(p)
    db.add_all(patients)
    db.flush()

    # --- feedback over 180 days. Month index 0 = oldest. Bad month for waiting time at index 3; improvement after.
    n_cases, case_pool = 0, []
    for i in range(450):
        age = rnd.randint(0, 179)
        month = 5 - age // 30
        r = rnd.random()
        neg_cut = 0.13 + (0.10 if month == 3 else 0) - (0.03 if month >= 4 else 0)
        sentiment = "negative" if r < neg_cut else "neutral" if r < neg_cut + 0.20 else "positive"
        rating = {"negative": rnd.choice([1, 2, 2]), "neutral": 3, "positive": rnd.choice([4, 5, 5])}[sentiment]
        p = rnd.choice(patients)
        text_, trans, themes, summary = "", "", [], ""
        has_text = sentiment != "positive" and rnd.random() < 0.7 or rnd.random() < 0.2
        lang = p.language
        if has_text and sentiment == "positive":
            if lang == "ar" or rnd.random() < 0.25:
                text_, trans = rnd.choice(POS_AR)
                lang = "ar"
            else:
                text_ = trans = rnd.choice(POS_EN)
            summary = "Positive comment about care and staff"
        elif has_text:
            theme = "Waiting time" if month == 3 and rnd.random() < 0.6 else rnd.choice(list(NEG_EN))
            if lang == "ar" and rnd.random() < 0.6:
                key = rnd.choice(list(NEG_AR))
                text_, trans = rnd.choice(NEG_AR[key])
                themes = key.split("+")
            else:
                text_ = trans = rnd.choice(NEG_EN[theme])
                themes = [theme]
            summary = trans.rstrip(".")[:100]
        urgency = "high" if rating == 1 else "medium" if sentiment == "negative" else "low"
        owner = D.THEME_OWNER.get(themes[0], "Front office") if themes else "Front office"
        created = now() - timedelta(days=age, hours=rnd.randint(0, 20))
        ai = {"sentiment": sentiment, "score": {"negative": -0.6, "neutral": 0, "positive": 0.7}[sentiment], "themes": themes,
              "new_themes": [], "urgency": urgency, "translation_en": trans, "summary": summary or f"Rated {rating}/5, no comment",
              "suggested_owner": owner, "provider": "precomputed"}
        fb = FeedbackResponse(patient_id=p.id, department_id=p.department_id, rating=rating,
                              answers={k: min(5, max(1, rating + rnd.randint(-1, 1))) for k in Q_KEYS}, text=text_, language=lang,
                              created_at=created, ai=ai, sentiment=sentiment, themes=themes, urgency=urgency, reviewed=age > 14)
        db.add(fb)
        if sentiment == "negative" or (sentiment == "neutral" and text_ and rnd.random() < 0.5):
            case_pool.append((fb, owner))
    db.flush()

    # --- ~60 cases: 8 open in SLA, 6 overdue, rest resolved/closed
    pro = users["patient_relations"]
    pool = [x for x in case_pool if x[0].text] + [x for x in case_pool if not x[0].text]
    pool = pool[:60]
    pool.sort(key=lambda x: x[0].created_at, reverse=True)
    for n_cases, (fb, owner) in enumerate(pool, 1):
        i = n_cases - 1
        open_ok, overdue = i < 8, 8 <= i < 14
        age = (now() - fb.created_at)
        status = (rnd.choice(["New", "Assigned", "In investigation"]) if open_ok else
                  rnd.choice(["Assigned", "In investigation"]) if overdue else rnd.choice(["Resolved", "Closed", "Closed"]))
        due = (now() + timedelta(hours=rnd.randint(6, 60)) if open_ok else now() - timedelta(hours=rnd.randint(5, 70)) if overdue
               else fb.created_at + timedelta(hours=D.SLA[fb.urgency]))
        c = Case(number=f"CS-{1000 + n_cases}", feedback_id=fb.id, patient_id=fb.patient_id, department_id=dep[owner].id,
                 title=fb.ai["summary"][:200], urgency=fb.urgency, status=status, owner_id=None if status == "New" else pro.id,
                 due_at=due, created_at=fb.created_at, breach_notified=overdue)
        if status in ("Resolved", "Closed"):
            c.closed_at = fb.created_at + timedelta(hours=rnd.randint(12, 200 if fb.created_at.month == (now() - timedelta(days=60)).month else 110))
            c.resolution = "Reviewed with the department and patient contacted."
        db.add(c)
        db.flush()
        fb.case_id = c.id
        db.add(CaseEvent(case_id=c.id, kind="created", text=f"Case opened from feedback (rating {fb.rating}/5)", created_at=fb.created_at))
        if c.owner_id:
            db.add(CaseEvent(case_id=c.id, kind="assigned", text=f"Assigned to {pro.name}", actor="System", created_at=fb.created_at + timedelta(minutes=2)))
        if overdue:
            db.add(CaseEvent(case_id=c.id, kind="escalated", text="SLA breached; escalated to Quality Manager", created_at=due))
        if c.closed_at:
            db.add(CaseEvent(case_id=c.id, kind="closed", text=f"Closed: {c.resolution}", actor=pro.name, created_at=c.closed_at))
    db.commit()


def main():
    with SessionLocal() as db:
        if "--if-empty" in sys.argv:
            try:
                if db.scalar(select(Tenant.id).limit(1)):
                    print("Data present, skipping seed.")
                    return
            except Exception:
                db.rollback()
        rebuild(db)
        print("Seed complete.")


if __name__ == "__main__":
    main()

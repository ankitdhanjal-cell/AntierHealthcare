"""Rebuilds the sandbox from scratch:  python -m app.seed   (add --if-empty to skip when data exists)."""
import random
import uuid
import sys

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from . import defaults as D
from .db import Base, SessionLocal, engine
from .models import Department, Role, Setting, Site, Tenant, User
from .security import hash_password
from .seed_feedback import generate
from .seed_incidents import generate as generate_incidents
from .seed_quality import generate as generate_quality

PASSWORD = "Sandbox@2026"
USERS = [
    ("Layla Al-Harthy", "quality.manager@hospital.example", "quality_manager", []),
    ("Omar Al-Balushi", "patient.relations@hospital.example", "patient_relations", []),
    ("Dr. Salim Al-Rawahi", "dept.head@hospital.example", "department_head", ["OPD", "Emergency"]),
    ("Nadia Fernandes", "infection.control@hospital.example", "infection_control", ["Inpatient wards", "ICU"]),
    ("Hessa Al-Mamari", "nurse.manager@hospital.example", "nurse_manager", ["Inpatient wards", "ICU"]),
    ("Priya Menon", "staff@hospital.example", "staff_reporter", ["Inpatient wards"]),
    ("Maryam Al-Kharusi", "staff.maternity@hospital.example", "staff_reporter", ["Maternity", "Paediatrics"]),
    ("Vikram Pillai", "staff.diagnostics@hospital.example", "staff_reporter", ["Radiology", "Laboratory", "Operating Theatre"]),
    ("Khalid Al-Siyabi", "front.desk@hospital.example", "front_desk", ["Front office"]),
    ("Fatma Al-Lawati", "management@hospital.example", "management_viewer", []),
    ("Admin User", "admin@hospital.example", "admin", []),
]

def rebuild(db: Session):
    db.rollback()
    db.close()
    rnd = random.Random(2026)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db.expire_all()
    db.add(Tenant(id="t1", name="Demo Hospital", branding={"primary_color": "#0f766e", "sender_name": "Antier Healthcare Suite", "logo_url": ""},
                  profile={"timezone": "Asia/Muscat", "beds": 120, "type": "Private hospital", "deployment_note": "Runs on the hospital's own server or an approved cloud region."}))
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
        users[role if role not in users else email.split('@')[0]] = u  # first user of a role keeps the role key
    db.flush()

    generate(db, rnd, dep, users)
    generate_incidents(db, rnd, dep, users)
    generate_quality(db, rnd, dep, users)
    db.commit()

def schema_is_current() -> bool:
    """False when the database is missing a table or column that the models define (no migrations, so we rebuild)."""
    insp = inspect(engine)
    have = set(insp.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in have or {c.name for c in table.columns} - {c["name"] for c in insp.get_columns(table.name)}:
            return False
    return True


def main():
    with SessionLocal() as db:
        if "--if-empty" in sys.argv:
            try:
                if db.scalar(select(Tenant.id).limit(1)):
                    if schema_is_current():
                        print("Data present, skipping seed.")
                        return
                    print("Database schema is out of date; rebuilding sandbox data.")
            except Exception:
                db.rollback()
        rebuild(db)
        print("Seed complete.")

if __name__ == "__main__":
    main()

"""Incidents, investigations and corrective actions for the sandbox (about 60 over six months).

Texts are in seed_data/incident_texts.json. One serious event is under investigation with a full root cause analysis, and one
OPD near miss carries the corrective action that explains the improvement in waiting-time complaints.
"""
import json
import random
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import defaults as D
from sqlalchemy import select

from .models import AuditLog, Capa, Case, CaseEvent, FeedbackResponse, Incident, IncidentEvent, now

TZ = ZoneInfo("Asia/Muscat")
DATA = json.loads((Path(__file__).parent / "seed_data" / "incident_texts.json").read_text(encoding="utf-8"))
FACTORS = {  # short generic contributing factors used on closed investigations
    "falls": {"people": ["Patient did not call for help"], "environment": ["Bed area not clear of obstacles"]},
    "medication": {"process": ["Independent check not completed at that step"], "communication": ["Information not carried through handover"]},
    "patient_identification": {"process": ["Two-identifier check skipped under time pressure"]},
    "pressure_injury": {"process": ["Repositioning not completed or recorded on schedule"], "equipment": ["Pressure-relieving surface not matched to risk"]},
    "equipment": {"equipment": ["Fault not detected at the scheduled check"], "process": ["No expiry or function line on the checklist"]},
    "infection": {"process": ["Bundle step missed or delayed"], "people": ["Hand hygiene or PPE not followed"]},
    "other": {"process": ["No safeguard at peak times"]},
}


def _dt(rnd: random.Random, age_days: int, used: set) -> datetime:
    base = (datetime.now(TZ) - timedelta(days=age_days)).date()
    for _ in range(50):
        dt = datetime.combine(base, time(rnd.randint(0, 23), rnd.randint(0, 59), rnd.randint(0, 59)), TZ)
        if dt <= datetime.now(TZ) - timedelta(minutes=30) and dt not in used:
            used.add(dt)
            return dt.astimezone(ZoneInfo("UTC"))
    dt = datetime.now(TZ) - timedelta(minutes=30 + len(used))
    used.add(dt)
    return dt.astimezone(ZoneInfo("UTC"))


def generate(db, rnd: random.Random, dep: dict, users: dict):
    sla = D.INCIDENT_SLA
    used: set = set()
    qm = users["quality_manager"]
    # people who really work in a department report from it (a head of OPD does not report a fall on a ward)
    staff_in = {}
    for role_or_key, u in users.items():
        if u.role_id in ("quality_manager", "patient_relations", "management_viewer", "admin"):
            continue
        for did in u.department_ids or []:
            staff_in.setdefault(did, []).append(u)
    investigators = {"infection": users["infection_control"], "OPD": users["department_head"], "Emergency": users["department_head"],
                     "Inpatient wards": users["nurse_manager"], "ICU": users["nurse_manager"]}
    entries = [dict(zip(("category", "dept", "location", "harm", "age", "text", "action", "title"), e)) for e in DATA["incidents"]]
    entries.sort(key=lambda e: -e["age"])  # oldest first so numbers rise with time
    audit_rows, n_open_old = [], 0
    for n, e in enumerate(entries, 1):
        age, harm, cat = e["age"], e["harm"], e["category"]
        occurred = _dt(rnd, age, used)
        created = min(occurred + timedelta(hours=rnd.randint(1, 9), minutes=rnd.randint(0, 59)), now() - timedelta(minutes=5))
        anonymous = rnd.random() < 0.2
        reporter = rnd.choice(staff_in.get(dep[e["dept"]].id) or [qm])
        inv = investigators.get(cat) or investigators.get(e["dept"]) or qm
        if age <= 6:
            status = "Reported"
        elif age <= 20:
            status = rnd.choice(["Triaged", "Under investigation", "Actions open"])
        elif n_open_old < 3 and e["category"] in ("falls", "medication", "equipment") and harm in ("mild", "moderate", "no_harm") and 20 < age < 70:
            status, n_open_old = "Actions open", n_open_old + 1
        else:
            status = "Closed"
        due = created + timedelta(hours=sla[harm])
        i = Incident(number=f"INC-{2000 + n}", title=e["title"], description=e["text"], category=cat, harm=harm, status=status,
                     department_id=dep[e["dept"]].id, location=e["location"], occurred_at=occurred, created_at=created,
                     immediate_action=e["action"], anonymous=anonymous, reported_by=None if anonymous else reporter.id, due_at=due,
                     sentinel=harm in D.SENTINEL_HARM, ai={"category": cat, "harm": harm, "summary": e["title"], "provider": "precomputed", "status": "ok"})
        if status != "Reported":
            i.investigator_id = inv.id
        db.add(i)
        db.flush()
        who = "Anonymous reporter" if anonymous else reporter.name
        events = [("reported", "Incident reported", who, created)]
        audit_rows.append(AuditLog(at=created, user_id=None if anonymous else reporter.id, user_name=who, module="incidents", action="create", record_type="incident",
                                   record_id=i.id, summary=f"Incident {i.number} reported", after={"category": cat, "harm": harm}))
        if status != "Reported":
            events.append(("triaged", f"Triaged: investigator {inv.name}", qm.name, created + timedelta(hours=rnd.randint(2, 20))))
        capas = []
        if status != "Reported" and (harm not in ("near_miss", "no_harm") or rnd.random() < 0.55):
            tmpls = DATA["capa_templates"][cat]
            for k in range(1 if harm in ("near_miss", "no_harm") else rnd.randint(1, 2)):
                text = f"{tmpls[(n + k) % len(tmpls)].rstrip('.')}: {e['location']} first, after {i.number}."
                cdue = created + timedelta(days=rnd.randint(10, 35))
                c = Capa(incident_id=i.id, kind="corrective" if k == 0 else "preventive", action=text, owner_id=(inv if rnd.random() < 0.6 else qm).id, due_at=cdue, created_at=created + timedelta(days=1))
                capas.append(c)
        if status == "Closed":
            i.root_cause = f"{DATA['root_causes'][cat]} {e['title']}."
            i.contributing_factors = FACTORS[cat]
            i.closed_at = min(created + timedelta(hours=max(24, int(sla[harm] * rnd.uniform(0.35, 0.95)))), now() - timedelta(minutes=10))
            for c in capas:
                c.status, c.completed_at = "Completed", min(c.due_at - timedelta(days=rnd.randint(0, 6)), i.closed_at)
                c.check_due_at = c.completed_at + timedelta(days=60)
                if c.check_due_at < now() and rnd.random() < 0.85:
                    c.check_result = "effective"
                    c.check_note = "Repeat audit showed the change in place with no further events."
            events.append(("closed", "Incident closed", qm.name, i.closed_at))
            audit_rows.append(AuditLog(at=i.closed_at, user_id=qm.id, user_name=qm.name, module="incidents", action="status", record_type="incident",
                                       record_id=i.id, summary=f"{i.number} → Closed", before={"status": "Actions open"}, after={"status": "Closed"}))
        elif status in ("Under investigation", "Actions open") and harm in ("moderate", "mild"):
            i.root_cause = f"{DATA['root_causes'][cat]} {e['title']}."
        if status == "Actions open":
            overdue_set = n_open_old and age > 20
            for c in capas:
                c.status = rnd.choice(["Open", "In progress"])
                if overdue_set:
                    c.due_at, c.overdue_notified = now() - timedelta(days=rnd.randint(2, 9)), True
            if overdue_set:
                i.breach_notified = True
        if due < now() and status != "Closed":
            i.breach_notified = True
        for kind, text, actor, at in events:
            db.add(IncidentEvent(incident_id=i.id, kind=kind, text=text, actor=actor, at=at))
        db.add_all(capas)
        for c in capas:
            if c.status == "Completed":
                owner = next((u for u in users.values() if u.id == c.owner_id), qm)
                audit_rows.append(AuditLog(at=c.completed_at, user_id=owner.id, user_name=owner.name, module="incidents", action="capa_update", record_type="capa",
                                           record_id=c.id, summary=f"Action completed on {i.number}", before={"status": "In progress"}, after={"status": "Completed"}))
        # the OPD near miss behind the improvement in waiting-time complaints
        if e["location"] == "OPD waiting area":
            for c in capas:
                c.action = ("Re-space clinic start times across OPD and add a triage nurse in the waiting area at peak hours "
                            f"(follow-up to {i.number}).")
                c.owner_id, c.status = users["department_head"].id, "Completed"
                c.completed_at = now() - timedelta(days=62)
                c.check_due_at, c.check_result = now() - timedelta(days=5), "effective"
                c.check_note = "OPD waiting-time complaints fell sharply in the two months after the change."
                audit_rows.append(AuditLog(at=c.completed_at, user_id=users["department_head"].id, user_name=users["department_head"].name, module="incidents",
                                           action="capa_update", record_type="capa", record_id=c.id, summary=f"Action completed on {i.number}: OPD clinic start times re-spaced"))
    _sentinel(db, rnd, dep, users, used, audit_rows, len(entries) + 1)
    _from_complaints(db, rnd, dep, users, audit_rows, len(entries) + 2)
    db.add_all(audit_rows)


def _sentinel(db, rnd, dep, users, used, audit_rows, n):
    s = DATA["sentinel"]
    qm, nurse_mgr = users["quality_manager"], users["nurse_manager"]
    owners = [nurse_mgr, nurse_mgr, qm, users["admin"]]  # ward actions to the ward manager, staffing policy to quality, lighting to facilities
    occurred = (datetime.now(TZ) - timedelta(days=s["age"])).replace(hour=2, minute=15, second=0, microsecond=0).astimezone(ZoneInfo("UTC"))
    created = occurred + timedelta(minutes=50)
    i = Incident(number=f"INC-{2000 + n}", title=s["title"], description=s["description"], category=s["category"], harm=s["harm"], status="Under investigation",
                 department_id=dep[s["department"]].id, location=s["location"], occurred_at=occurred, created_at=created, immediate_action=s["immediate_action"],
                 reported_by=nurse_mgr.id, investigator_id=qm.id, due_at=created + timedelta(hours=D.INCIDENT_SLA[s["harm"]]), sentinel=True,
                 escalated_at=created + timedelta(hours=5), contributing_factors=s["factors"], why_chain=s["whys"], root_cause=s["root_cause"],
                 ai={"category": s["category"], "harm": s["harm"], "summary": s["title"], "provider": "precomputed", "status": "ok"})
    db.add(i)
    db.flush()
    db.add(IncidentEvent(incident_id=i.id, kind="reported", text="Incident reported (serious event)", actor=nurse_mgr.name, at=created))
    db.add(IncidentEvent(incident_id=i.id, kind="triaged", text=f"Triaged: harm Severe, investigator {qm.name}", actor=qm.name, at=created + timedelta(hours=1)))
    db.add(IncidentEvent(incident_id=i.id, kind="escalated", text="Escalated to management", actor=qm.name, at=i.escalated_at))
    for label, text in s["facts"]:
        day = int(label.split("d")[0].lstrip("-"))
        hh, mm = map(int, label.split(" ")[1].split(":"))
        at = (datetime.now(TZ) - timedelta(days=day)).replace(hour=hh, minute=mm, second=0, microsecond=0).astimezone(ZoneInfo("UTC"))
        db.add(IncidentEvent(incident_id=i.id, kind="fact", text=text, actor=qm.name, at=at))
    for k, (kind, text, state, days) in enumerate(s["capas"]):
        c = Capa(incident_id=i.id, kind=kind, action=text, owner_id=owners[k % len(owners)].id, due_at=now() + timedelta(days=days), created_at=created + timedelta(days=1))
        if state == "completed":
            c.status, c.completed_at, c.check_due_at = "Completed", now() - timedelta(hours=6), now() + timedelta(days=60)
        elif state == "in_progress":
            c.status = "In progress"
        db.add(c)
    audit_rows.append(AuditLog(at=created, user_id=nurse_mgr.id, user_name=nurse_mgr.name, module="incidents", action="create",
                               record_type="incident", record_id=i.id, summary=f"Serious event {i.number} reported", after={"category": s["category"], "harm": s["harm"]}))
    audit_rows.append(AuditLog(at=i.escalated_at, user_id=qm.id, user_name=qm.name, module="incidents", action="escalate", record_type="incident", record_id=i.id,
                               summary=f"{i.number} escalated to management"))


LINK_THEMES = {"Nursing care": ("other", "Patient raised a nursing care concern that the Quality team treated as a safety incident."),
               "Doctor communication": ("other", "Communication with the patient and family about the plan did not meet the standard."),
               "Cleanliness": ("infection", "Cleanliness of the patient area was below the standard and raised an infection control concern."),
               "Discharge process": ("medication", "Discharge medicines or instructions were incomplete and could have caused harm."),
               "Food": ("other", "A meal did not match the patient's recorded dietary needs.")}


def _from_complaints(db, rnd, dep, users, audit_rows, n):
    """A few closed complaints that were raised as incidents, so the link shows on both records."""
    qm = users["quality_manager"]
    db.flush()
    rows = db.execute(select(Case, FeedbackResponse).join(FeedbackResponse, FeedbackResponse.id == Case.feedback_id)
                      .where(Case.status.in_(["Resolved", "Closed"]), Case.incident_id.is_(None)).order_by(Case.created_at.desc())).all()
    seen, picked = set(), []
    for c, f in rows:
        theme = (f.themes or [""])[0]
        if theme in LINK_THEMES and theme not in seen and (now() - c.created_at).days > 5:
            seen.add(theme)
            picked.append((c, f, theme))
    for c, f, theme in picked[:5]:
        cat, why = LINK_THEMES[theme]
        text = (f.ai or {}).get("translation_en") or f.text
        raised = c.created_at + timedelta(hours=rnd.randint(3, 20))
        closed = min(c.closed_at or raised, now() - timedelta(minutes=30)) + timedelta(hours=rnd.randint(2, 30))
        closed = min(closed, now() - timedelta(minutes=20))
        harm = rnd.choice(["no_harm", "no_harm", "mild"])
        inv = users["nurse_manager"] if c.department_id in (users["nurse_manager"].department_ids or []) else qm
        i = Incident(number=f"INC-{2000 + n}", title=f"Complaint {c.number}: {c.title}"[:300], description=f"Raised from complaint {c.number}. Patient feedback: {text}", category=cat, harm=harm,
                     status="Closed", department_id=c.department_id, location="", occurred_at=c.created_at, created_at=raised, immediate_action="Patient contacted and the concern recorded.",
                     reported_by=qm.id, investigator_id=inv.id, due_at=raised + timedelta(hours=D.INCIDENT_SLA[harm]), patient_id=c.patient_id, case_id=c.id,
                     root_cause=why, contributing_factors={"process": ["The standard routine was not followed at the time"]}, closed_at=closed,
                     ai={"category": cat, "harm": harm, "summary": c.title, "provider": "precomputed", "status": "ok"})
        n += 1
        db.add(i)
        db.flush()
        c.incident_id = i.id
        db.add(CaseEvent(case_id=c.id, kind="incident", text=f"Incident {i.number} raised from this case", actor=qm.name, created_at=raised))
        for kind, t, who, at in (("reported", "Incident raised from a complaint case", qm.name, raised), ("linked", f"Linked to complaint case {c.number}", qm.name, raised),
                                 ("closed", "Incident closed", qm.name, closed)):
            db.add(IncidentEvent(incident_id=i.id, kind=kind, text=t, actor=who, at=at))
        audit_rows.append(AuditLog(at=raised, user_id=qm.id, user_name=qm.name, module="cases", action="raise_incident", record_type="case", record_id=c.id, summary=f"{c.number} → incident {i.number}"))
        audit_rows.append(AuditLog(at=closed, user_id=qm.id, user_name=qm.name, module="incidents", action="status", record_type="incident", record_id=i.id,
                                   summary=f"{i.number} → Closed", before={"status": "Under investigation"}, after={"status": "Closed"}))

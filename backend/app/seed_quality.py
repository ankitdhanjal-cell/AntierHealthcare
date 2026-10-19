"""Accreditation standards, evidence, audits and indicators for the sandbox.

The standards are a generic sample set written for this product, not the text of any real accreditation programme.
"""
import json
import random
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import select

from .config import settings as cfg
from .indicators_calc import completed_periods, last_periods
from .models import (AuditAnswer, AuditLog, AuditRun, AuditTemplate, Capa, Evidence, Incident, Indicator, IndicatorValue, QualityAction, Setting, StandardChapter,
                     StandardElement, TracerResult, TracerRun, now)

DATA = Path(__file__).parent / "seed_data"
STANDARDS = json.loads((DATA / "standards.json").read_text(encoding="utf-8"))["chapters"]
AUDITS = json.loads((DATA / "audit_templates.json").read_text(encoding="utf-8"))["templates"]
NOT_APPLICABLE = {"CAR.3.3", "GOV.3.2", "ENV.3.3", "STF.1.2", "RGT.2.3"}
NOT_MET = {"INF.3.3", "ENV.1.1", "STF.2.2", "GOV.2.2", "MED.1.2", "RGT.3.3"}
PARTIAL = {"INF.1.3", "QUA.2.3", "MED.3.2", "CAR.1.3", "CAR.2.3", "RGT.3.2", "ENV.2.2", "STF.3.1", "STF.2.3", "GOV.1.3", "QUA.1.3"}
DOC_TYPES = ["Policy", "Procedure", "Committee minutes", "Audit summary", "Training record", "Inspection checklist", "Register extract"]
GAP_NOTES = {
    "INF.3.3": "No outbreak drill has been held in the last 12 months.", "ENV.1.1": "Only one evacuation drill is recorded this year.",
    "STF.2.2": "Basic life support has lapsed for 14 clinical staff.", "GOV.2.2": "Nine policies in the sample are past their review date.",
    "MED.1.2": "Fridge temperature logs have gaps on weekends.", "RGT.3.3": "Complaint themes were not reviewed in the last quarter.",
    "INF.1.3": "Compliance met the target in three of the last six months.", "QUA.2.3": "Some effectiveness checks are overdue.",
}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def write_pdf(path: Path, title: str, meta: list[str], paragraphs: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 6)] + [Paragraph(m, styles["Italic"]) for m in meta] + [Spacer(1, 14)]
    story += [x for p in paragraphs for x in (Paragraph(p, styles["BodyText"]), Spacer(1, 8))]
    SimpleDocTemplate(str(path), pagesize=A4, title=title, author="Quality Department").build(story)


def reset_evidence_dir():
    root = Path(cfg.evidence_dir)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def generate_accreditation(db, rnd: random.Random, dep: dict, users: dict):
    root = reset_evidence_dir()
    db.merge(Setting(tenant_id="t1", key="accreditation", value={"name": "National Accreditation Survey", "survey_date": (date.today() + timedelta(days=100)).isoformat()}))
    owners = {r: users[r] for r in ("quality_manager", "patient_relations", "department_head", "infection_control", "admin")}
    elements = []
    for ci, ch in enumerate(STANDARDS):
        chapter = StandardChapter(code=ch["code"], name=ch["name"], position=ci)
        db.add(chapter)
        db.flush()
        n = 0
        for st in ch["standards"]:
            for k, text in enumerate(st["elements"], 1):
                n += 1
                code = f"{st['code']}.{k}"
                status = "Not applicable" if code in NOT_APPLICABLE else "Not met" if code in NOT_MET else "Partially met" if code in PARTIAL else "Met"
                owner = owners[ch["owner"]] if rnd.random() < 0.7 else owners[rnd.choice(list(owners))]
                reviewed = None if status == "Not applicable" else now() - timedelta(days=rnd.randint(8, 150) if status != "Not met" else rnd.randint(150, 230))
                e = StandardElement(chapter_id=chapter.id, standard_code=st["code"], standard_title=st["title"], code=code, text=text, owner_id=owner.id,
                                    status=status, last_reviewed_at=reviewed, note=GAP_NOTES.get(code, ""), position=n)
                db.add(e)
                elements.append((e, ch))
    db.flush()
    qm = users["quality_manager"]
    names = {u.id: u.name for u in users.values()}
    # evidence files: one controlled document per met element, a second for some, and partial evidence for partially met ones
    for i, (e, ch) in enumerate(elements):
        if e.status not in ("Met", "Partially met"):
            continue
        docs = 1 + (1 if e.status == "Met" and rnd.random() < 0.3 else 0)
        for d in range(docs):
            kind = DOC_TYPES[(i + d * 3) % len(DOC_TYPES)]
            when = now() - timedelta(days=rnd.randint(20, 300))
            title = f"{kind}: {e.standard_title}" if d == 0 else f"{kind}: {ch['name']} ({when:%b %Y})"
            fname = f"{slug(title)}.pdf"
            rel = f"{e.id}/{fname}"
            owner_name = names[e.owner_id]
            write_pdf(root / rel, title, [f"Controlled document · Version {rnd.randint(1, 4)}.{rnd.randint(0, 3)} · Effective {when:%d %b %Y}",
                                          f"Owner: {owner_name} · Reviewed by the Quality Committee"],
                      [f"Standard {e.code}: {e.text}", f"This {kind.lower()} records how the organisation meets the element above for {ch['name'].lower()}. "
                       "It describes responsibilities, the frequency of checks, how results are recorded and who receives them.",
                       "Staff are made aware of this document at orientation and when it changes. The next review is due within twelve months of the effective date."])
            db.add(Evidence(element_id=e.id, kind="file", title=title, filename=fname, path=rel, added_by=owners[ch["owner"]].name, created_at=when))
    # completed corrective actions linked as evidence (one click in the product)
    by_code = {e.code: e for e, _ in elements}
    link = {"falls": "CAR.1.2", "medication": "MED.3.2", "infection": "INF.2.3", "equipment": "ENV.2.3", "patient_identification": "QUA.2.2", "pressure_injury": "CAR.1.3"}
    done = {}
    for c, i in db.execute(select(Capa, Incident).join(Incident, Incident.id == Capa.incident_id).where(Capa.status == "Completed", Capa.check_result == "effective").order_by(Capa.completed_at.desc())):
        if i.category in link and i.category not in done:
            done[i.category] = c
            e = by_code[link[i.category]]
            db.add(Evidence(element_id=e.id, kind="capa", title=f"Corrective action {i.number}: {c.action[:140]}", source_id=c.id, added_by=qm.name, created_at=c.completed_at))
    # gap actions
    n_act = 0
    for e, ch in elements:
        if e.status in ("Not met", "Partially met") and ch["code"] != "INF" and (e.status == "Not met" or rnd.random() < 0.4):  # the mock survey raises the INF actions
            overdue = n_act == 1
            db.add(QualityAction(text=f"Close the gap for {e.code}: {e.note or e.text}", source_type="gap", element_id=e.id, owner_id=e.owner_id,
                                 due_at=now() + timedelta(days=-6 if overdue else rnd.randint(7, 60)), status=rnd.choice(["Open", "In progress"]),
                                 created_by=qm.name, created_at=now() - timedelta(days=rnd.randint(10, 40)), overdue_notified=overdue))
            n_act += 1
    # one completed mock survey of the infection prevention chapter with findings turned into actions
    chap = db.scalar(select(StandardChapter).where(StandardChapter.code == "INF"))
    run = TracerRun(chapter_id=chap.id, started_by=qm.name, started_at=now() - timedelta(days=21), completed_at=now() - timedelta(days=21, hours=-3))
    db.add(run)
    db.flush()
    for e, ch in elements:
        if ch["code"] != "INF":
            continue
        note = GAP_NOTES.get(e.code, "")
        r = TracerResult(run_id=run.id, element_id=e.id, result=e.status, note=note)
        if e.status in ("Not met", "Partially met"):
            a = QualityAction(text=f"Close the gap for {e.code}: {note}", source_type="tracer", source_id=run.id, element_id=e.id, owner_id=e.owner_id,
                              due_at=now() + timedelta(days=rnd.randint(10, 40)), status="In progress", created_by=qm.name, created_at=run.started_at)
            db.add(a)
            db.flush()
            r.action_id = a.id
        db.add(r)
    db.add(AuditLog(at=run.started_at, user_id=qm.id, user_name=qm.name, module="accreditation", action="tracer_complete", record_type="chapter",
                    record_id=chap.id, summary="Mock survey completed for Infection Prevention and Control"))
    return elements


HH_UNITS = [("Inpatient wards", "Ward 2"), ("Inpatient wards", "Ward 3"), ("Inpatient wards", "Ward 4"), ("ICU", "ICU"),
            ("Emergency", "Emergency department"), ("Maternity", "Maternity ward"), ("OPD", "OPD clinics")]
OTHER_UNITS = {"Environmental cleaning": [("Inpatient wards", "Ward 2"), ("Inpatient wards", "Ward 3"), ("Inpatient wards", "Ward 4"), ("ICU", "ICU")],
               "Sharps and waste": [("Inpatient wards", "Ward 3"), ("Emergency", "Emergency department"), ("Laboratory", "Phlebotomy room")],
               "Isolation precautions": [("Inpatient wards", "Ward 4"), ("ICU", "ICU")],
               "Medication storage": [("Inpatient wards", "Ward 2"), ("Inpatient wards", "Ward 3"), ("Emergency", "Emergency department")]}


def _items(tpl: dict) -> list[dict]:
    if "moments" in tpl:
        return [{"key": f"m{m}-{o}", "text": f"Moment {m} · {name} (observation {o})"} for m, name in enumerate(tpl["moments"], 1) for o in range(1, tpl["observations"] + 1)]
    return [{"key": f"i{n}", "text": t} for n, t in enumerate(tpl["items"], 1)]


def _month_end(period: str):
    y, m = map(int, period.split("-"))
    return datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc) - timedelta(minutes=1)


def generate_audits(db, rnd: random.Random, dep: dict, users: dict):
    inf = users["infection_control"]
    periods = last_periods(6)  # oldest .. current month
    tpls = {}
    for t in AUDITS:
        row = AuditTemplate(name=t["name"], description=t["description"], items=_items(t), target=t["target"])
        db.add(row)
        tpls[t["name"].split(" (")[0]] = (row, t)
    db.flush()
    runs = []  # (run, template row, tpl json)
    audit_rows = []

    def add_run(name, dept, unit, period, score, overdue=False, scheduled=False):
        row, tpl = tpls[name]
        due = _month_end(period)
        r = AuditRun(template_id=row.id, department_id=dep[dept].id, unit=unit, period=period, due_at=due, auditor_id=inf.id)
        if scheduled or overdue:
            r.status = "Scheduled"
        else:
            r.status, r.completed_at = "Completed", min(due - timedelta(days=rnd.randint(1, 20)), now() - timedelta(hours=3))
            n = len(row.items)
            na = rnd.randint(0, 5) if n >= 20 else rnd.randint(0, 1)  # not every opportunity or question applies, so counts differ from audit to audit
            seen = n - na
            yes = max(1, min(seen, round(score / 100 * seen + rnd.uniform(-0.45, 0.45))))
            if name.startswith("Hand hygiene"):
                while 100 * yes / seen < 70.5 and yes < seen:
                    yes += 1
                while 100 * yes / seen > 94.5 and yes > 1:
                    yes -= 1
            r.yes_count, r.no_count, r.score = yes, seen - yes, round(100 * yes / seen, 1)
            r.comment = ""
        db.add(r)
        db.flush()
        if r.status == "Completed":
            order = ["yes"] * r.yes_count + ["no"] * r.no_count + ["na"] * (len(row.items) - r.yes_count - r.no_count)
            rnd.shuffle(order)
            for it, res in zip(row.items, order):
                db.add(AuditAnswer(run_id=r.id, item_key=it["key"], result=res, comment=rnd.choice(tpl["findings"]) if res == "no" else ""))
            t = row.name
            audit_rows.append(AuditLog(at=r.completed_at, user_id=inf.id, user_name=inf.name, module="audits", action="complete", record_type="audit", record_id=r.id,
                                       summary=f"{t} completed for {r.unit} {r.period}: {r.score}%", after={"score": r.score}))
            runs.append((r, row, tpl))
        return r

    # hand hygiene: monthly per ward. Ward 4 trends down, Emergency runs lowest, ICU highest. One audit overdue, three of this month still to do.
    base = {"Ward 2": 86, "Ward 3": 89, "Ward 4": 92, "ICU": 93, "Emergency department": 77, "Maternity ward": 88, "OPD clinics": 84}
    hh_periods = last_periods(13)  # a year of hand hygiene audits, so the run chart has something to show
    for dept, unit in HH_UNITS:
        for k, p in enumerate(hh_periods):
            score = base[unit] + rnd.uniform(-2.5, 2.5) - max(0, k - 5) * 1.3  # compliance slips over the second half of the year
            if unit == "Ward 4":
                score = 92 - max(0, k - 7) * 4.0 + rnd.uniform(-1.5, 1.5)
            score = max(70, min(95, score))
            current = k == len(hh_periods) - 1
            if current and unit not in ("Ward 2", "ICU", "Maternity ward"):
                add_run("Hand hygiene", dept, unit, p, 0, scheduled=True)
            elif k == len(hh_periods) - 2 and unit == "ICU":
                add_run("Hand hygiene", dept, unit, p, 0, overdue=True)
            else:
                add_run("Hand hygiene", dept, unit, p, score)
    # other templates, last three months
    for name, units in OTHER_UNITS.items():
        recent = periods[-2:] if name != "Environmental cleaning" else periods[-3:]
        for dept, unit in units:
            for k, p in enumerate(recent):
                if name == "Environmental cleaning" and unit == "Ward 3" and p == periods[-2]:
                    add_run(name, dept, unit, p, 0, overdue=True)
                elif p == periods[-1] and (unit, name) not in {("ICU", "Environmental cleaning"), ("Ward 2", "Medication storage")}:
                    add_run(name, dept, unit, p, 0, scheduled=True)
                else:
                    add_run(name, dept, unit, p, rnd.choice([100, 96, 93, 89, 87, 83]) if name != "Sharps and waste" else rnd.choice([100, 97, 93, 90, 86]))
    # actions raised from "No" answers on a few recent audits
    n_act = 0
    for r, row, tpl in sorted(runs, key=lambda x: x[0].completed_at, reverse=True):
        if n_act >= 6 or r.period not in periods[-3:]:
            continue
        a = db.scalar(select(AuditAnswer).where(AuditAnswer.run_id == r.id, AuditAnswer.result == "no", AuditAnswer.comment != ""))
        if not a:
            continue
        text = next(i["text"] for i in row.items if i["key"] == a.item_key)
        act = QualityAction(text=f"Correct: {a.comment or text} ({row.name}, {r.unit} {r.period})", source_type="audit", source_id=r.id, department_id=r.department_id, owner_id=inf.id,
                            due_at=now() + timedelta(days=rnd.randint(-4, 21)), status=rnd.choice(["Open", "In progress"]), created_by=inf.name, created_at=r.completed_at)
        db.add(act)
        db.flush()
        a.action_id = act.id
        n_act += 1
    db.add_all(audit_rows)
    return runs


INDICATORS = [
    # key, name, definition, numerator, denominator, multiplier, unit, target, amber, direction, source, auto, owner role
    ("satisfaction", "Patient satisfaction", "Average overall star rating given by patients after discharge.", "Sum of overall ratings (1 to 5)", "Number of feedback responses received", 1, "/ 5", 4.0, 3.8, "higher",
     "Patient feedback form (calculated)", "satisfaction", "patient_relations"),
    ("closure_time", "Average complaint closure time", "Average time from a complaint case being opened to being closed.", "Total hours from case opened to closed", "Cases closed in the month", 1, "h", 72, 96, "lower",
     "Cases (calculated)", "closure_time", "patient_relations"),
    ("sla_closure", "Complaints closed within SLA", "Share of complaint cases closed on or before their due date.", "Cases closed on or before the due date", "Cases closed in the month", 100, "%", 90, 80, "higher",
     "Cases (calculated)", "sla_closure", "quality_manager"),
    ("hand_hygiene", "Hand hygiene compliance", "Share of observed hand hygiene opportunities where hand hygiene was performed correctly (WHO 5 moments).", "Opportunities with correct hand hygiene", "Opportunities observed", 100, "%", 90, 85, "higher",
     "Monthly hand hygiene audits (calculated)", "hand_hygiene", "infection_control"),
    ("falls_rate", "Inpatient falls per 1,000 patient days", "Falls in inpatient areas, any harm level, per 1,000 occupied bed days.", "Number of inpatient falls", "Inpatient days in the month", 1000, "per 1,000 patient days", 2.5, 3.5, "lower",
     "Incident reports and bed census", "", "quality_manager"),
    ("hai_rate", "Hospital-acquired infection rate", "Healthcare-associated infections confirmed by infection control, per 1,000 occupied bed days.", "Confirmed hospital-acquired infections", "Inpatient days in the month", 1000, "per 1,000 patient days", 1.5, 2.0, "lower",
     "Infection control surveillance", "", "infection_control"),
    ("patient_id", "Patient identification compliance", "Observed checks where two patient identifiers were confirmed before care, sampling, or medicines.", "Checks with two identifiers confirmed", "Checks observed", 100, "%", 95, 90, "higher",
     "Monthly observation audit", "", "quality_manager"),
    ("wait_consult", "Average waiting time to consultation (OPD)", "Average time from registration to the start of the consultation for sampled OPD patients.", "Total waiting minutes in the sample", "Patients sampled", 1, "min", 30, 40, "lower",
     "OPD queue sample", "", "department_head"),
    ("med_errors", "Medication errors per 1,000 admissions", "Medication errors that reached the patient, per 1,000 admissions.", "Medication errors reaching the patient", "Admissions in the month", 1000, "per 1,000 admissions", 3.0, 4.0, "lower",
     "Incident reports and admissions register", "", "infection_control"),
    ("pressure_injury", "Hospital-acquired pressure injuries", "New pressure injuries of stage 2 or above developed after admission, per 1,000 occupied bed days.", "New hospital-acquired pressure injuries", "Inpatient days in the month", 1000, "per 1,000 patient days", 0.8, 1.2, "lower",
     "Skin assessment records", "", "quality_manager"),
]


def _manual_values(key: str, k: int, rnd: random.Random):
    """Pattern for month k of 12 (0 = oldest). Returns (numerator, denominator)."""
    pdays = rnd.randint(2350, 2750)
    adm = rnd.randint(640, 760)
    if key == "falls_rate":  # steady, then a sustained rise: the run chart flags a shift above the median
        rate = rnd.uniform(1.5, 2.1) if k < 6 else rnd.uniform(2.7, 3.5)
        return round(rate * pdays / 1000), pdays
    if key == "hai_rate":
        return round(rnd.uniform(1.0, 1.9) * pdays / 1000), pdays
    if key == "patient_id":  # improving after a retraining campaign
        n = rnd.randint(380, 460)
        pct = rnd.uniform(89, 93) if k < 5 else rnd.uniform(94, 98)
        return round(pct / 100 * n), n
    if key == "wait_consult":  # a bad patch in months 6-7 and recovery after re-spacing clinic starts
        n = rnd.randint(150, 220)
        minutes = rnd.uniform(46, 56) if k in (6, 7) else rnd.uniform(26, 34) if k >= 9 else rnd.uniform(31, 40)
        return round(minutes * n), n
    if key == "med_errors":
        return max(1, round(rnd.uniform(1.8, 4.4) * adm / 1000)), adm
    if key == "pressure_injury":
        return round(rnd.uniform(0.4, 1.4) * pdays / 1000), pdays
    return 1, 1


def generate_indicators(db, rnd: random.Random, users: dict):
    by_key, owner_name = {}, {}
    for pos, (key, name, definition, num, den, mult, unit, target, amber, direction, source, auto, owner) in enumerate(INDICATORS):
        ind = Indicator(key=key, name=name, definition=definition, numerator=num, denominator=den, multiplier=mult, unit=unit, target=target, amber=amber,
                        direction=direction, source=source, auto=auto, owner_id=users[owner].id, position=pos)
        db.add(ind)
        by_key[key], owner_name[key] = ind, users[owner].name
    db.flush()
    periods = completed_periods(12)
    # Older months of the patient-feedback indicators were kept in the hospital's spreadsheets before this system, and were imported.
    # Months that have records in the system always use the records.
    for key in ("satisfaction", "closure_time", "sla_closure"):
        ind = by_key[key]
        for k, p in enumerate(periods[:6]):
            n = rnd.randint(120, 170)
            if key == "satisfaction":
                num, den = round(n * rnd.uniform(3.75, 4.05), 1), n
            elif key == "closure_time":
                den = rnd.randint(16, 28)
                num = round(den * rnd.uniform(44, 72), 1)
            else:
                den = rnd.randint(16, 28)
                num = round(den * rnd.uniform(0.6, 0.82))
            db.add(IndicatorValue(indicator_id=ind.id, period=p, numerator=num, denominator=den, note="Imported from the previous spreadsheet", entered_by="Data import",
                                  entered_at=now() - timedelta(days=(12 - k) * 28)))
    for key, ind in by_key.items():
        if ind.auto:
            continue
        for k, p in enumerate(periods):
            n, d = _manual_values(key, k, rnd)
            if key == "wait_consult" and k in (6, 7):
                note = "Peak-hour queues in OPD; corrective action agreed."
            elif key == "wait_consult" and k == 9:
                note = "Clinic start times re-spaced and triage nurse added."
            else:
                note = ""
            when = now() - timedelta(days=(12 - k) * 28)
            db.add(IndicatorValue(indicator_id=ind.id, period=p, numerator=n, denominator=d, note=note, entered_by=owner_name[key], entered_at=when))
            if k >= 9:
                db.add(AuditLog(at=when, user_name=owner_name[key], module="indicators", action="value", record_type="indicator", record_id=ind.id,
                                summary=f"{ind.name} {p}: {round(n / d * ind.multiplier, 2)} {ind.unit}", after={"numerator": n, "denominator": d}))


def attach_audit_evidence(db, runs, elements, users):
    """Completed audits linked as evidence to the elements they support."""
    by_code = {e.code: e for e, _ in elements}
    qm = users["quality_manager"]
    picks = {"INF.1.2": "Hand hygiene", "INF.2.3": "Environmental cleaning", "MED.1.1": "Medication storage", "ENV.3.2": "Sharps and waste", "INF.3.2": "Isolation precautions"}
    for code, tname in picks.items():
        found = [r for r, row, tpl in runs if row.name.startswith(tname)]
        if not found:
            continue
        r = max(found, key=lambda x: x.completed_at)
        row = db.get(AuditTemplate, r.template_id)
        db.add(Evidence(element_id=by_code[code].id, kind="audit_run", title=f"Audit: {row.name}, {r.unit}, {r.period} ({r.score:.0f}% compliance)", source_id=r.id, added_by=qm.name, created_at=r.completed_at))


def generate(db, rnd: random.Random, dep: dict, users: dict):
    elements = generate_accreditation(db, rnd, dep, users)
    runs = generate_audits(db, rnd, dep, users)
    db.flush()
    attach_audit_evidence(db, runs, elements, users)
    generate_indicators(db, rnd, users)

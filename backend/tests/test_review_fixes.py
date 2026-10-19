"""Fixes from the role-by-role review: drill-downs, scoping, seed realism."""
import re
from sqlalchemy import select

from app.models import AuditLog, AuditRun, Case, FeedbackResponse, Incident, Patient, User
from tests.test_incidents import login


def total(c, path):
    return c.get(path + ("&" if "?" in path else "?") + "size=1").json()["total"]


def test_patient_relations_home_numbers_match_their_links(client):
    pr = login(client, "patient.relations@hospital.example")
    h = pr.get("/api/home").json()
    for key, link in h["links"].items():
        if key in ("open", "overdue", "new_today", "due_today", "awaiting_callback"):
            assert total(pr, "/api" + link) == h["counts"][{"open": "open", "overdue": "overdue", "new_today": "new_today", "due_today": "due_today", "awaiting_callback": "awaiting_callback"}[key]], key
    assert total(pr, "/api" + h["links"]["feedback_today"]) == h["counts"]["feedback_today"]


def test_department_head_sees_emergency_cases_and_nothing_filed_elsewhere(client, db):
    dh = login(client, "dept.head@hospital.example")
    cases = dh.get("/api/cases?size=100").json()["items"]
    assert {c["department"] for c in cases} == {"OPD", "Emergency"}
    # every case sits in the same department as its feedback, so "Open case" never leads to "not found"
    for c in db.scalars(select(Case)):
        fb = db.get(FeedbackResponse, c.feedback_id)
        assert c.department_id == fb.department_id


def test_department_scoped_audits_funnel_and_actions(client):
    dh = login(client, "dept.head@hospital.example")
    units = {r["department"] for r in dh.get("/api/audits/runs?size=200").json()["items"]}
    assert units <= {"OPD", "Emergency"}
    assert dh.get("/api/audits/runs?size=1").json()["total"] < client.get("/api/audits/runs?size=1").json()["total"]
    assert dh.get("/api/analytics/funnel").json()["steps"][1]["value"] < client.get("/api/analytics/funnel").json()["steps"][1]["value"]
    assert len(dh.get("/api/actions").json()) < len(client.get("/api/actions").json())
    h = dh.get("/api/home").json()
    assert total(dh, "/api/audits/runs?" + h["links"]["audits_due"].split("?")[1]) == h["counts"]["audits_due"]
    assert total(dh, "/api" + h["links"]["rating_30d"]) == h["counts"]["responses_30d"]


def test_funnel_responses_equal_dashboard_responses(client):
    assert client.get("/api/analytics/funnel").json()["steps"][1]["value"] == client.get("/api/dashboard").json()["responses"]


def test_staff_reporter_sees_only_own_reports_and_no_cases(client):
    sr = login(client, "staff@hospital.example")
    items = sr.get("/api/incidents?size=100").json()["items"]
    assert items and all(i["reporter"] == "Priya Menon" for i in items)
    assert sr.get("/api/cases").status_code == 403 and sr.get("/api/dashboard").status_code == 403
    assert sr.get("/api/actions").status_code == 403
    h = sr.get("/api/home").json()
    assert h["kind"] == "reporter" and h["counts"]["total"] == len(items)
    assert all(c["incident_number"] in {i["number"] for i in items} for c in sr.get("/api/incidents/capas").json())


def test_403_message_is_plain(client):
    r = login(client, "staff@hospital.example").get("/api/accreditation/summary")
    assert r.status_code == 403 and "role" not in r.json()["detail"].lower() and "'" not in r.json()["detail"]


def test_role_homes(client):
    assert login(client, "management@hospital.example").get("/api/home").json()["kind"] == "management"
    ic = login(client, "infection.control@hospital.example").get("/api/home").json()
    assert ic["kind"] == "audit" and ic["compliance"] and {i["key"] for i in ic["indicators"]} == {"hand_hygiene", "hai_rate"}
    assert login(client, "infection.control@hospital.example").get("/api/audits/templates").status_code == 200


def test_infection_control_can_schedule_and_edit_templates(client):
    ic = login(client, "infection.control@hospital.example")
    t = ic.get("/api/audits/templates").json()[0]
    assert ic.put(f"/api/audits/templates/{t['id']}", json={"name": t["name"], "description": t["description"], "items": [i["text"] for i in t["items"]], "target": t["target"]}).status_code == 200


def test_reassign_list_only_people_who_can_act(client):
    people = client.get("/api/cases/meta/assignees").json()
    assert people and not {"Fatma Al-Lawati", "Khalid Al-Siyabi"} & {p["name"] for p in people}
    mgmt = next(u for u in client.get("/api/users").json() if u["name"] == "Fatma Al-Lawati")
    case = client.get("/api/cases?open=true&size=1").json()["items"][0]
    assert client.post(f"/api/cases/{case['id']}/assign", json={"owner_id": mgmt["id"]}).status_code == 422


def test_every_open_case_has_an_owner(db):
    assert not db.scalars(select(Case).where(Case.status.notin_(["Resolved", "Closed"]), Case.owner_id.is_(None))).all()


def test_seed_realism(db):
    users = {u.id: u for u in db.scalars(select(User))}
    # nobody reports from a department they do not work in
    for inc in db.scalars(select(Incident)):
        if int(inc.number[4:]) <= 2065 and inc.reported_by and users[inc.reported_by].role_id not in ("quality_manager",):  # seeded ones; other tests add their own
            assert inc.department_id in (users[inc.reported_by].department_ids or []), inc.number
    assert sum(i.anonymous for i in db.scalars(select(Incident))) >= 8
    seeded = {i.id for i in db.scalars(select(Incident)) if int(i.number[4:]) <= 2065}
    linked = [c for c in db.scalars(select(Case)) if c.incident_id in seeded]
    assert len(linked) >= 4 and all(c.status in ("Resolved", "Closed") for c in linked)
    staff = {u.name for u in users.values()}
    assert not [p for p in db.scalars(select(Patient)) if p.name in staff]
    arabic = [p for p in db.scalars(select(Patient)) if p.language == "ar" and p.mrn != "WALKUP"]
    assert all(re.match(r"^(Mohammed|Ahmed|Fatima|Aisha|Khalid|Salma|Yusuf|Mariam|Hamad|Noor|Rashid|Huda|Said|Zahra|Badar|Amna|Faisal|Shamsa) Al-", p.name) for p in arabic)
    runs = [r for r in db.scalars(select(AuditRun)) if r.status == "Completed"]
    assert len({round(r.score) % 5 for r in runs}) > 2  # scores are not all multiples of 5
    modules = set(db.scalars(select(AuditLog.module)))
    assert {"audits", "indicators", "incidents", "cases"} <= modules


def test_audit_trail_readable(client):
    mods = client.get("/api/audit/modules").json()
    assert "incidents" in mods and "audits" in mods
    rows = client.get("/api/audit?module=incidents&size=100").json()["items"]
    assert not any(re.search(r"[0-9a-f]{32}", str(r["before"]) + str(r["after"])) for r in rows)


def test_no_duplicate_story_in_open_cases(client):
    titles = [c["title"].lower() for c in client.get("/api/cases?open=true&size=100").json()["items"]]
    for key in ("call bell", "sick child", "medication"):
        assert sum(key in t for t in titles) <= 1, key


def test_inbox_can_show_only_responses_with_a_comment(client):
    everything = total(client, "/api/feedback")
    with_text = total(client, "/api/feedback?has_comment=true")
    assert 0 < with_text < everything
    assert all(i["summary"] and not i["summary"].startswith("Rated") for i in client.get("/api/feedback?has_comment=true&size=15").json()["items"])


def test_indicators_have_a_year_of_history_and_hand_hygiene_shows_a_shift(client):
    inds = {i["key"]: i for i in client.get("/api/indicators").json()}
    for i in inds.values():
        assert len(client.get(f"/api/indicators/{i['id']}").json()["series"]) >= 8, i["key"]
    hh = client.get(f"/api/indicators/{inds['hand_hygiene']['id']}").json()
    assert len(hh["series"]) == 12 and hh["shift"] and hh["shift"]["length"] >= 6 and hh["shift_label"] == "worsening"

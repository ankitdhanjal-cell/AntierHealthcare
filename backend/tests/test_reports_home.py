import time

from tests.test_incidents import login


def last_period(client):
    return client.get("/api/reports/committee").json()[0]["period"]


def test_committee_pack_pdf_is_branded_and_fast(client):
    p = last_period(client)
    assert client.put(f"/api/reports/committee/{p}/note", json={"cover_note": "Waiting times recovered; falls need attention."}).status_code == 200
    t = time.time()
    r = client.get(f"/api/reports/committee/{p}/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert time.time() - t < 10 and len(r.content) > 8000
    assert "committee-pack" in r.headers["content-disposition"]
    prev = client.get(f"/api/reports/committee/{p}").json()
    assert prev["cover_note"].startswith("Waiting") and len(prev["kpis"]) == 10 and prev["charts"] >= 6


def test_committee_pack_exports_without_a_cover_note(client):
    p = client.get("/api/reports/committee").json()[3]["period"]  # a month nobody has written a note for
    r = client.get(f"/api/reports/committee/{p}/pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_committee_pack_rejects_bad_or_current_month(client):
    assert client.get("/api/reports/committee/2026-13/pdf").status_code == 422
    assert client.get("/api/reports/committee/2099-01/pdf").status_code == 422


def test_committee_pack_needs_reports_permission(client):
    fd = login(client, "front.desk@hospital.example")
    assert fd.get("/api/reports/committee").status_code == 403


def test_tasks_list_what_is_assigned_to_me(client):
    t = client.get("/api/tasks").json()
    assert t["total"] > 0 and all("href" in x and x["kind"] for x in t["items"])
    due = [x["due_at"] for x in t["items"] if x["due_at"]]
    assert due == sorted(due)  # soonest first
    sr = login(client, "staff@hospital.example")
    assert all(x["kind"] in ("Case", "Incident", "Corrective action", "Effectiveness check") for x in sr.get("/api/tasks").json()["items"])


def test_role_based_homes(client):
    qm = client.get("/api/home").json()
    assert qm["kind"] == "quality" and qm["readiness"]["pct"] > 0 and qm["days_left"] is not None and qm["counts"]["overdue_actions"] >= 1
    assert isinstance(qm["off_target"], list)
    pr = login(client, "patient.relations@hospital.example").get("/api/home").json()
    assert pr["kind"] == "patient_relations" and pr["cases"] and "awaiting_callback" in pr["counts"]
    dh = login(client, "dept.head@hospital.example").get("/api/home").json()
    assert dh["kind"] == "department" and dh["scoped"] and set(dh["departments"]) == {"OPD", "Emergency"}
    full = client.get("/api/cases?open=true&size=1").json()["total"]
    assert dh["counts"]["open_cases"] < full

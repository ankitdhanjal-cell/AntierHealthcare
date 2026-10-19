from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Capa, Incident


def login(client, email):
    from fastapi.testclient import TestClient
    c = TestClient(client.app)
    token = c.post("/api/auth/login", json={"email": email, "password": "Sandbox@2026"}).json()["token"]
    c.headers.update({"authorization": f"Bearer {token}"})
    return c


def when(hours_ago=3):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def test_seed_shape(db):
    inc = list(db.scalars(select(Incident)))
    assert 55 <= len(inc) <= 70
    assert len({i.description for i in inc}) == len(inc)
    near = sum(i.harm in ("near_miss", "no_harm") for i in inc)
    assert near / len(inc) > 0.55
    sentinel = [i for i in inc if i.sentinel]
    assert len(sentinel) == 1 and sentinel[0].root_cause and sentinel[0].why_chain and sentinel[0].escalated_at
    assert db.scalar(select(Capa).where(Capa.incident_id == sentinel[0].id).limit(1))
    ward2 = [i for i in inc if i.category == "falls" and i.location.startswith("Ward 2") and (datetime.now(timezone.utc) - i.occurred_at).days <= 90]
    assert len(ward2) >= 3  # "3 similar falls on Ward 2 in 90 days"


def test_report_and_full_lifecycle(client):
    r = client.post("/api/incidents", json={"description": "Patient found on the floor beside the bed, grazed knee. Call bell was in reach.", "occurred_at": when(), "harm": "mild"})
    assert r.status_code == 200
    iid = r.json()["id"]
    d = client.get(f"/api/incidents/{iid}").json()
    assert d["status"] == "Reported" and d["category"] == "falls" and not d["sentinel"]
    people = client.get("/api/incidents/meta").json()["people"]
    t = client.put(f"/api/incidents/{iid}/triage", json={"investigator_id": people[0]["id"], "accept": True})
    assert t.status_code == 200 and client.get(f"/api/incidents/{iid}").json()["status"] == "Under investigation"
    # cannot close without a root cause
    assert client.post(f"/api/incidents/{iid}/status", json={"status": "Closed"}).status_code == 422
    assert client.put(f"/api/incidents/{iid}/investigation", json={"root_cause": "Footwear unsuitable.", "why_chain": ["a", "b"], "contributing_factors": {"people": ["x"]}}).status_code == 200
    # moderate and above need an action
    client.put(f"/api/incidents/{iid}/triage", json={"harm": "moderate"})
    assert client.post(f"/api/incidents/{iid}/status", json={"status": "Closed"}).status_code == 422
    c = client.post(f"/api/incidents/{iid}/capas", json={"kind": "corrective", "action": "Provide non-slip socks to all patients at risk", "due_at": when(-48)})
    assert c.status_code == 200
    assert client.put(f"/api/incidents/capas/{c.json()['id']}", json={"check_result": "effective"}).status_code == 422  # not completed yet
    assert client.put(f"/api/incidents/capas/{c.json()['id']}", json={"status": "Completed"}).status_code == 200
    assert client.put(f"/api/incidents/capas/{c.json()['id']}", json={"check_result": "effective"}).status_code == 200
    assert client.post(f"/api/incidents/{iid}/status", json={"status": "Closed"}).status_code == 200
    assert client.get(f"/api/incidents/{iid}").json()["status"] == "Closed"
    assert client.put(f"/api/incidents/{iid}/investigation", json={"root_cause": "x"}).status_code == 409


def test_serious_event_must_be_escalated_before_closing(client):
    r = client.post("/api/incidents", json={"description": "Patient fell and suffered a fracture, transferred to theatre for surgery.", "occurred_at": when()})
    iid = r.json()["id"]
    assert r.json()["sentinel"] is True
    assert client.get(f"/api/incidents/{iid}").json()["harm"] == "severe"
    client.put(f"/api/incidents/{iid}/investigation", json={"root_cause": "Reassessment not triggered."})
    client.post(f"/api/incidents/{iid}/capas", json={"action": "Reassess falls risk after sedation", "due_at": when(-48)})
    assert client.post(f"/api/incidents/{iid}/status", json={"status": "Closed"}).status_code == 422
    assert client.post(f"/api/incidents/{iid}/escalate").status_code == 200
    assert client.post(f"/api/incidents/{iid}/escalate").status_code == 409
    assert client.post(f"/api/incidents/{iid}/status", json={"status": "Closed"}).status_code == 200


def test_raise_incident_from_case_links_both_records(client):
    case = client.get("/api/cases?open=true&size=1").json()["items"][0]
    r = client.post(f"/api/cases/{case['id']}/raise-incident")
    assert r.status_code == 200
    inc = client.get(f"/api/incidents/{r.json()['incident_id']}").json()
    assert inc["case"]["id"] == case["id"] and inc["patient"] and inc["department"] != "—"
    assert client.get(f"/api/cases/{case['id']}").json()["incident"]["number"] == r.json()["number"]
    assert client.post(f"/api/cases/{case['id']}/raise-incident").status_code == 409


def test_future_time_rejected_and_validation(client):
    assert client.post("/api/incidents", json={"description": "Something happened", "occurred_at": when(-5)}).status_code == 422
    assert client.post("/api/incidents", json={"description": "short", "occurred_at": when()}).status_code == 422


def test_roles_front_desk_reports_but_cannot_list(client):
    fd = login(client, "front.desk@hospital.example")
    assert fd.post("/api/incidents", json={"description": "Spill in the front lobby not signed for 20 minutes.", "occurred_at": when()}).status_code == 200
    assert fd.get("/api/incidents").status_code == 403
    assert fd.get("/api/incidents/meta").status_code == 200


def test_staff_reporter_sees_only_own_and_cannot_triage(client):
    sr = login(client, "staff@hospital.example")
    r = sr.post("/api/incidents", json={"description": "Wrong-size syringe stocked in the clean utility room.", "occurred_at": when()})
    mine = sr.get("/api/incidents?size=100").json()["items"]
    assert r.json()["id"] in [i["id"] for i in mine]
    assert all(i["department"] == "Inpatient wards" or i["reporter"] == "Priya Menon" for i in mine)
    assert sr.put(f"/api/incidents/{r.json()['id']}/triage", json={"accept": True}).status_code == 403


def test_anonymous_report_hides_reporter(client):
    r = client.post("/api/incidents", json={"description": "Colleague skipped hand hygiene between patients twice.", "occurred_at": when(), "anonymous": True})
    d = client.get(f"/api/incidents/{r.json()['id']}").json()
    assert d["reporter"] == "Anonymous" and d["anonymous"] is True

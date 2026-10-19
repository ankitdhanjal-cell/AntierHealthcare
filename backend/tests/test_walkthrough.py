"""The acceptance walkthrough from the brief, end to end through the API."""
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def test_discharge_to_committee_pack(client):
    anon = TestClient(client.app)
    # 1. discharge event sends the feedback request
    pid = client.get("/api/integrations/his/patients").json()[0]["id"]
    assert client.post("/api/integrations/his/discharge", json={"patient_id": pid, "send_now": True}).status_code == 200
    token = client.get(f"/api/whatsapp/messages?patient_id={pid}").json()[-1]["link"].split("/f/")[1]
    # 2. the patient answers in Arabic with a complaint; AI tags it
    form = anon.get(f"/api/public/feedback/{token}").json()
    assert form["answered"] is False
    r = anon.post(f"/api/public/feedback/{token}", json={"rating": 1, "nps": 2, "language": "ar", "answers": {}, "text": "انتظار طويل جداً وفاتورة غير واضحة، تجربة سيئة."}).json()
    assert r["case_opened"] is True and r["google"] is False
    # 3. a case exists with English themes; the call-back is logged
    case = client.get("/api/cases?size=1").json()["items"][0]
    detail = client.get(f"/api/cases/{case['id']}").json()
    assert detail["feedback"]["language"] == "ar" and set(detail["feedback"]["themes"]) >= {"Waiting time", "Billing"} and detail["feedback"]["translation"]
    assert client.post(f"/api/cases/{case['id']}/call", json={"outcome": "reached", "note": "Apologised and explained the bill"}).status_code == 200
    # 4. one click to an incident, linked both ways
    inc = client.post(f"/api/cases/{case['id']}/raise-incident").json()
    assert client.get(f"/api/cases/{case['id']}").json()["incident"]["number"] == inc["number"]
    # 5. investigate, add an action, complete it
    people = client.get("/api/incidents/meta").json()["people"]
    client.put(f"/api/incidents/{inc['incident_id']}/triage", json={"investigator_id": people[0]["id"], "accept": True})
    client.put(f"/api/incidents/{inc['incident_id']}/investigation", json={"root_cause": "Single registration counter open at peak time."})
    due = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    capa = client.post(f"/api/incidents/{inc['incident_id']}/capas", json={"action": "Open a second registration counter between 09:00 and 12:00", "due_at": due}).json()["id"]
    assert client.put(f"/api/incidents/capas/{capa}", json={"status": "Completed"}).status_code == 200
    # 6. attach it as accreditation evidence: readiness moves
    before = client.get("/api/accreditation/summary").json()
    gap = next(g for g in before["gaps"] if g["status"] == "Not met")
    att = client.post(f"/api/accreditation/elements/{gap['id']}/attach", json={"source_type": "capa", "source_id": capa, "mark_met": True})
    assert att.status_code == 200 and att.json()["readiness"]["pct"] > before["readiness"]["pct"]
    # 7. the committee pack exports quickly
    period = client.get("/api/reports/committee").json()[0]["period"]
    t = time.time()
    pdf = client.get(f"/api/reports/committee/{period}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and time.time() - t < 10

import io
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Capa, Evidence


def test_seed_readiness_and_evidence(client, db):
    s = client.get("/api/accreditation/summary").json()
    r = s["readiness"]
    assert 68 <= r["pct"] <= 80 and r["counts"]["Not met"] >= 3 and s["met_without_evidence"] == 0
    assert 95 <= s["days_left"] <= 105 and len(s["chapters"]) == 8 and s["gaps"]
    assert sum(c["applicable"] for c in s["chapters"]) == r["applicable"]
    assert db.scalar(select(Evidence).where(Evidence.kind == "capa").limit(1))


def test_status_change_moves_readiness(client):
    before = client.get("/api/accreditation/summary").json()["readiness"]["pct"]
    gap = client.get("/api/accreditation/summary").json()["gaps"][0]
    assert client.put(f"/api/accreditation/elements/{gap['id']}", json={"status": "Met"}).status_code == 200
    after = client.get("/api/accreditation/summary").json()["readiness"]["pct"]
    assert after > before
    assert client.put(f"/api/accreditation/elements/{gap['id']}", json={"status": "Bogus"}).status_code == 422


def test_upload_and_download_evidence(client):
    el = client.get("/api/accreditation/elements?status=Met").json()[0]
    r = client.post(f"/api/accreditation/elements/{el['id']}/evidence", files={"file": ("policy.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")}, data={"title": "Test policy"})
    assert r.status_code == 200
    ev = [v for v in client.get(f"/api/accreditation/elements/{el['id']}").json()["evidence"] if v["title"] == "Test policy"][0]
    d = client.get(f"/api/accreditation/evidence/{ev['id']}/download")
    assert d.status_code == 200 and d.content.startswith(b"%PDF")
    bad = client.post(f"/api/accreditation/elements/{el['id']}/evidence", files={"file": ("run.exe", io.BytesIO(b"x"), "application/octet-stream")})
    assert bad.status_code == 422
    assert client.delete(f"/api/accreditation/evidence/{ev['id']}").status_code == 200


def test_attach_closed_capa_as_evidence_moves_readiness(client, db):
    capa = db.scalars(select(Capa).where(Capa.status == "Completed")).all()[-1]
    gap = [g for g in client.get("/api/accreditation/summary").json()["gaps"] if g["status"] == "Not met"][0]
    before = client.get("/api/accreditation/summary").json()["readiness"]["pct"]
    r = client.post(f"/api/accreditation/elements/{gap['id']}/attach", json={"source_type": "capa", "source_id": capa.id, "mark_met": True})
    assert r.status_code == 200 and r.json()["readiness"]["pct"] > before
    assert client.post(f"/api/accreditation/elements/{gap['id']}/attach", json={"source_type": "capa", "source_id": capa.id}).status_code == 409
    open_capa = db.scalars(select(Capa).where(Capa.status != "Completed")).first()
    assert client.post(f"/api/accreditation/elements/{gap['id']}/attach", json={"source_type": "capa", "source_id": open_capa.id}).status_code == 422


def test_mock_survey_finding_becomes_action_in_two_calls(client):
    ch = client.get("/api/accreditation/summary").json()["chapters"][0]["id"]
    run = client.post("/api/accreditation/tracers", json={"chapter_id": ch}).json()["id"]
    el = client.get(f"/api/accreditation/tracers/{run}").json()["elements"][0]
    assert client.put(f"/api/accreditation/tracers/{run}/results/{el['id']}", json={"result": "Not met", "note": "Rights statement missing in Ward 4"}).status_code == 200
    a = client.post(f"/api/accreditation/tracers/{run}/results/{el['id']}/action", json={})
    assert a.status_code == 200
    t = client.get(f"/api/accreditation/tracers/{run}").json()
    assert t["elements"][0]["action"]["owner"] != "Unassigned" and t["progress"]["done"] == 1
    assert client.post(f"/api/accreditation/tracers/{run}/results/{el['id']}/action", json={}).status_code == 409
    el2 = t["elements"][1]
    client.put(f"/api/accreditation/tracers/{run}/results/{el2['id']}", json={"result": "Met"})
    assert client.post(f"/api/accreditation/tracers/{run}/results/{el2['id']}/action", json={}).status_code == 422
    assert client.post(f"/api/accreditation/tracers/{run}/complete").status_code == 200
    assert client.put(f"/api/accreditation/tracers/{run}/results/{el['id']}", json={"result": "Met"}).status_code == 404


def test_survey_date_and_actions(client):
    d = (datetime.now(timezone.utc) + timedelta(days=40)).date().isoformat()
    assert client.put("/api/accreditation/survey-date", json={"survey_date": d}).status_code == 200
    assert client.get("/api/accreditation/summary").json()["days_left"] in (39, 40, 41)
    assert client.put("/api/accreditation/survey-date", json={"survey_date": "31/12/2026"}).status_code == 422
    acts = client.get("/api/actions?overdue=true").json()
    assert acts and all(a["overdue"] for a in acts)

import io
from datetime import date

from sqlalchemy import select

from app.indicators_calc import completed_periods, run_chart
from app.models import AuditRun, AuditTemplate, now


def test_seed_audits(client, db):
    runs = list(db.scalars(select(AuditRun)))
    overdue = [r for r in runs if r.status != "Completed" and r.due_at < now()]
    assert len(overdue) == 2
    hh = db.scalar(select(AuditTemplate).where(AuditTemplate.name.like("Hand hygiene%")))
    done = [r for r in runs if r.template_id == hh.id and r.status == "Completed"]
    assert all(70 <= r.score <= 95 for r in done)
    ward4 = sorted([r for r in done if r.unit == "Ward 4"], key=lambda r: r.period)
    assert ward4[0].score - ward4[-1].score >= 10  # one ward trending down


def test_compliance_endpoint_and_target(client):
    hh = [t for t in client.get("/api/audits/templates").json() if t["name"].startswith("Hand hygiene")][0]
    c = client.get(f"/api/audits/compliance?template_id={hh['id']}&months=6").json()
    assert c["template"]["target"] == 90 and len(c["periods"]) == 6
    assert any(u["unit"] == "Ward 4" and u["change"] < -5 for u in c["units"])


def test_audit_run_workflow_and_action_from_no(client):
    tpl = [t for t in client.get("/api/audits/templates").json() if t["name"].startswith("Sharps")][0]
    unit = {"department_id": None, "unit": "Test unit"}
    period = completed_periods(1)[0]
    assert client.post("/api/audits/schedule", json={"template_id": tpl["id"], "units": [unit], "periods": [period]}).json()["created"] == 1
    assert client.post("/api/audits/schedule", json={"template_id": tpl["id"], "units": [unit], "periods": [period]}).json()["created"] == 0  # no duplicates
    run = client.get("/api/audits/runs?size=200").json()["items"]
    rid = [r for r in run if r["unit"] == "Test unit"][0]["id"]
    d = client.get(f"/api/audits/runs/{rid}").json()
    assert client.post(f"/api/audits/runs/{rid}/complete", json={}).status_code == 422  # unanswered
    answers = [{"key": it["key"], "result": "yes"} for it in d["items"]]
    answers[0] = {"key": d["items"][0]["key"], "result": "no", "comment": "Container above the fill line"}
    assert client.put(f"/api/audits/runs/{rid}/answers", json={"answers": answers}).status_code == 200
    assert client.put(f"/api/audits/runs/{rid}/answers", json={"answers": [{"key": "bogus", "result": "yes"}]}).status_code == 422
    r = client.post(f"/api/audits/runs/{rid}/complete", json={"comment": "ok"}).json()
    assert round(r["score"]) == round(100 * (len(answers) - 1) / len(answers)) and client.post(f"/api/audits/runs/{rid}/complete", json={}).status_code == 409
    assert client.post(f"/api/audits/runs/{rid}/answers/{answers[1]['key']}/action", json={}).status_code == 422  # a Yes cannot raise an action
    a = client.post(f"/api/audits/runs/{rid}/answers/{answers[0]['key']}/action", json={})
    assert a.status_code == 200 and client.post(f"/api/audits/runs/{rid}/answers/{answers[0]['key']}/action", json={}).status_code == 409
    # photo
    assert client.post(f"/api/audits/runs/{rid}/photo/{answers[0]['key']}", files={"file": ("x.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")}).status_code == 200
    assert client.get(f"/api/audits/runs/{rid}/photo/{answers[0]['key']}").status_code == 200
    # completed audit can be attached as evidence
    el = client.get("/api/accreditation/elements?status=Not met").json()[0]
    assert client.post(f"/api/accreditation/elements/{el['id']}/attach", json={"source_type": "audit_run", "source_id": rid, "mark_met": True}).status_code == 200


def test_template_edit_keeps_keys(client):
    t = [t for t in client.get("/api/audits/templates").json() if t["name"].startswith("Medication")][0]
    lines = [i["text"] for i in t["items"]] + ["A new question about labelling"]
    assert client.put(f"/api/audits/templates/{t['id']}", json={"name": t["name"], "description": "", "items": lines, "target": 95}).status_code == 200
    t2 = [x for x in client.get("/api/audits/templates").json() if x["id"] == t["id"]][0]
    assert [i["key"] for i in t2["items"][:-1]] == [i["key"] for i in t["items"]] and len(t2["items"]) == len(t["items"]) + 1


def test_dictionary_has_definitions_and_shift(client):
    inds = client.get("/api/indicators").json()
    assert 8 <= len(inds) <= 10
    for i in inds:
        assert i["definition"] and i["numerator"] and i["denominator"] and i["target"] is not None
    falls = [i for i in inds if i["key"] == "falls_rate"][0]
    assert falls["shift"] and falls["shift_label"] == "worsening" and falls["shift"]["length"] >= 6
    d = client.get(f"/api/indicators/{falls['id']}").json()
    assert len(d["series"]) == 12 and d["median"] is not None


def test_shift_rule_unit():
    pts = [{"value": v} for v in [1, 1, 1, 1, 1, 1, 5, 5, 5, 5, 5, 5]]
    assert run_chart(pts)["shift"]["side"] == "above"
    assert run_chart([{"value": v} for v in [1, 5, 1, 5, 1, 5, 1, 5, 1, 5, 1, 5]])["shift"] is None
    assert run_chart([])["median"] is None


def test_manual_entry_rules(client):
    ind = [i for i in client.get("/api/indicators").json() if i["key"] == "hai_rate"][0]
    p = date.today().strftime("%Y-%m")
    rows = client.get(f"/api/indicators/entry?period={p}").json()
    assert all(r["numerator_label"] for r in rows) and len(rows) >= 6
    assert client.put(f"/api/indicators/{ind['id']}/values", json={"period": p, "numerator": 3, "denominator": 2400}).json()["value"] == 1.25
    assert client.put(f"/api/indicators/{ind['id']}/values", json={"period": "2999-01", "numerator": 1, "denominator": 10}).status_code == 422
    assert client.put(f"/api/indicators/{ind['id']}/values", json={"period": p, "numerator": 1, "denominator": 0}).status_code == 422
    auto = [i for i in client.get("/api/indicators").json() if i["auto"]][0]
    assert client.put(f"/api/indicators/{auto['id']}/values", json={"period": p, "numerator": 1, "denominator": 10}).status_code == 422
    pct = [i for i in client.get("/api/indicators").json() if i["key"] == "patient_id"][0]
    assert client.put(f"/api/indicators/{pct['id']}/values", json={"period": p, "numerator": 11, "denominator": 10}).status_code == 422


def test_pareto_sorted_with_cumulative(client):
    for src in ("themes", "incident_categories"):
        p = client.get(f"/api/indicators/pareto?source={src}").json()
        counts = [i["count"] for i in p["items"]]
        assert counts == sorted(counts, reverse=True) and abs(p["items"][-1]["cumulative"] - 100) < 0.2 and p["vital_few"]
    assert client.get("/api/indicators/pareto?source=bogus").status_code == 422

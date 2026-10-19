from sqlalchemy import select

from app.models import FeedbackChannel, FeedbackResponse
from tests.test_incidents import login


def test_nps_overall_and_breakdowns(client):
    n = client.get("/api/analytics/nps?months=6").json()
    o = n["overall"]
    assert o["count"] > 400 and o["promoters"] + o["passives"] + o["detractors"] == o["count"]
    assert o["nps"] == round(100 * (o["promoters"] - o["detractors"]) / o["count"])
    assert n["by_department"] and n["by_doctor"] and all(d["count"] >= 5 for d in n["by_doctor"])
    assert [d["nps"] for d in n["by_department"]] == sorted((d["nps"] for d in n["by_department"]), reverse=True)


def test_funnel_steps_never_grow(client):
    f = client.get("/api/analytics/funnel?months=6").json()["steps"]
    vals = [s["value"] for s in f]
    assert vals == sorted(vals, reverse=True) and vals[0] > vals[1] > vals[2] >= vals[3] >= vals[4] > 0
    assert f[1]["pct_of_previous"] < 100


def test_compliments_list_and_share(client):
    c = client.get("/api/feedback/compliments").json()
    assert c["total"] >= 20 and c["top_staff"] and all(i["staff_mentions"] and i["sentiment"] == "positive" for i in c["items"])
    one = c["items"][0]
    r = client.post(f"/api/feedback/{one['id']}/share-compliment")
    assert r.status_code == 200 and r.json()["shared_with"]
    assert client.get("/api/feedback/compliments?shared=true").json()["total"] >= 1
    staff = c["top_staff"][0]["name"]
    assert all(staff in i["staff_mentions"] for i in client.get(f"/api/feedback/compliments?staff={staff}").json()["items"])


def test_preview_is_public_and_bilingual(client):
    from fastapi.testclient import TestClient
    anon = TestClient(client.app)
    en, ar = anon.get("/api/public/preview/en").json(), anon.get("/api/public/preview/ar").json()
    assert "Thank you for choosing" in en["whatsapp"] and "نشكرك" in ar["whatsapp"] and len(en["sms"]) <= 160 and len(ar["sms"]) <= 160
    assert len(en["questions"]) == 5 and ar["questions"][0]["label"] != en["questions"][0]["label"]


def test_qr_channel_to_form_to_response_with_nps(client, db):
    from fastapi.testclient import TestClient
    anon = TestClient(client.app)
    ch = db.scalars(select(FeedbackChannel)).first()
    assert anon.get(f"/api/public/channel/{ch.token}").json()["name"] == ch.name
    tok = anon.post(f"/api/public/channel/{ch.token}/start", json={"language": "ar"}).json()["token"]
    form = anon.get(f"/api/public/feedback/{tok}").json()
    assert form["language"] == "ar" and form["patient_first_name"] == ""  # no greeting for walk-up respondents
    r = anon.post(f"/api/public/feedback/{tok}", json={"rating": 5, "nps": 10, "answers": {}, "text": "Nurse Reem was kind and attentive, thank you."})
    assert r.status_code == 200 and r.json()["google"] is True
    fb = db.scalar(select(FeedbackResponse).where(FeedbackResponse.channel_id == ch.id).order_by(FeedbackResponse.created_at.desc()))
    assert fb.nps == 10 and "Nurse Reem" in fb.staff_mentions
    assert anon.post(f"/api/public/feedback/{tok}", json={"rating": 5, "nps": 11}).status_code in (409, 422)
    assert anon.get("/api/public/channel/nope").status_code == 404


def test_channel_management_and_qr_svg(client):
    chs = client.get("/api/channels").json()
    assert len(chs) >= 8 and all("/f/c/" in c["url"] for c in chs)
    svg = client.get(f"/api/channels/{chs[0]['id']}/qr.svg")
    assert svg.status_code == 200 and svg.headers["content-type"] == "image/svg+xml" and b"<svg" in svg.content
    dept = client.get("/api/incidents/meta").json()["departments"][0]["id"]
    admin = login(client, "admin@hospital.example")
    assert client.post("/api/channels", json={"name": "Dental clinic", "kind": "clinic", "department_id": dept}).status_code == 403  # settings admin only
    assert admin.post("/api/channels", json={"name": "Dental clinic", "kind": "clinic", "department_id": dept}).status_code == 200
    assert admin.post("/api/channels", json={"name": "X", "kind": "ward"}).status_code == 422
    assert login(client, "front.desk@hospital.example").get("/api/channels").status_code == 403


def test_sms_discharge_and_whatsapp_messages(client):
    pid = client.get("/api/integrations/his/patients").json()[0]["id"]
    r = client.post("/api/integrations/his/discharge", json={"patient_id": pid, "send_now": True, "channel": "sms"})
    assert r.status_code == 200
    msgs = client.get(f"/api/whatsapp/messages?patient_id={pid}").json()
    assert msgs[-1]["channel"] == "sms" and len(msgs[-1]["body"]) <= 160
    assert client.post("/api/integrations/his/discharge", json={"patient_id": pid, "channel": "pigeon"}).status_code == 422


def test_service_recovery_loop(client, db):
    closed = client.get("/api/cases?loop=closed&size=100").json()["items"]
    open_ = client.get("/api/cases?loop=open&size=100").json()["items"]
    assert closed and open_ and all(c["loop_closed"] for c in closed) and not any(c["loop_closed"] for c in open_)
    target = next(c for c in closed if not c["closing_message_at"])
    assert client.post(f"/api/cases/{target['id']}/closing-message").status_code == 200
    assert client.post(f"/api/cases/{target['id']}/closing-message").status_code == 409
    live = client.get("/api/cases?open=true&size=1").json()["items"][0]
    assert client.post(f"/api/cases/{live['id']}/closing-message").status_code == 422
    assert client.get(f"/api/cases/{target['id']}").json()["closing_message_at"]


def test_feedback_detail_has_hospital_fields(client):
    items = client.get("/api/feedback?size=100").json()["items"]
    inpatient = next(i for i in items if i["department"] == "Inpatient wards" and i["mrn"].startswith("MRN"))
    d = client.get(f"/api/feedback/{inpatient['id']}").json()
    assert d["token"] and d["attending"].startswith("Dr.") and d["mrn"].startswith("MRN") and d["ward"] and d["length_of_stay_days"] >= 1

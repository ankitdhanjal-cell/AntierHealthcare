"""Every dashboard figure must equal the number of records behind its drill-down link."""
from calendar import monthrange


def last_day(ym):
    y, m = map(int, ym.split("-"))
    return f"{ym}-{monthrange(y, m)[1]:02d}"


def total(client, path):
    return client.get(path + ("&" if "?" in path else "?") + "size=1").json()["total"]


def test_kpi_hrefs_match_values(client):
    d = client.get("/api/dashboard").json()
    kpis = {k["key"]: k for k in d["kpis"]}
    assert total(client, "/api" + kpis["satisfaction"]["href"]) == d["responses"]
    assert total(client, "/api" + kpis["cases_past_sla"]["href"]) == kpis["cases_past_sla"]["value"]
    assert total(client, "/api" + kpis["open_cases"]["href"]) == kpis["open_cases"]["value"]


def test_sentiment_and_theme_drilldowns(client):
    d = client.get("/api/dashboard").json()
    for name, n in d["sentiment"].items():
        assert total(client, f"/api/feedback?sentiment={name}&date_from={d['since']}") == n
    for t in d["top_themes"]:
        assert total(client, f"/api/feedback?theme={t['theme']}&not_positive=true&date_from={d['since']}") == t["count"]


def test_trend_months_match(client):
    d = client.get("/api/dashboard").json()
    for m in d["satisfaction_trend"]:
        assert total(client, f"/api/feedback?date_from={m['month']}-01&date_to={last_day(m['month'])}") == m["count"]
    for m in d["cases_trend"]:
        assert total(client, f"/api/cases?date_from={m['month']}-01&date_to={last_day(m['month'])}") == m["opened"]


def test_call_log_adds_timeline_event(client):
    case = client.get("/api/cases?open=true&size=1").json()["items"][0]
    assert client.post(f"/api/cases/{case['id']}/call", json={"outcome": "reached", "note": "Test"}).status_code == 200
    assert client.post(f"/api/cases/{case['id']}/call", json={"outcome": "bogus"}).status_code == 422
    assert any(e["kind"] == "call" for e in client.get(f"/api/cases/{case['id']}").json()["timeline"])


def test_bad_date_is_rejected(client):
    assert client.get("/api/cases?date_from=2026-02-31").status_code == 422

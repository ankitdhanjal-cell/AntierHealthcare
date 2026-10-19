"""Monthly Quality and Patient Safety Committee pack, built as a branded PDF with ReportLab (no browser needed)."""
import base64
import io
import re
from collections import Counter
from datetime import date

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from .defaults import HARM_LEVELS, INCIDENT_CATEGORIES
from .indicators_calc import completed_periods, rag, run_chart, series
from .models import AuditRun, AuditTemplate, Capa, FeedbackResponse, Incident, Indicator, QualityAction, StandardChapter, Tenant, User
from .services import hospital_tz, now, readiness

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
RAG = {"green": colors.HexColor("#0f9d6b"), "amber": colors.HexColor("#d97706"), "red": colors.HexColor("#dc4a3d"), "neutral": colors.grey}
RAG_TEXT = {"green": "On target", "amber": "Watch", "red": "Off target", "neutral": "—"}


def period_label(p: str) -> str:
    y, m = p.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def valid(p: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", p))


def fmt_value(ind: Indicator, v):
    if v is None:
        return "—"
    if ind.key == "closure_time":
        return f"{v / 24:.1f} days" if v >= 48 else f"{v:.0f} h"
    return f"{v}%" if ind.unit == "%" else f"{v} {ind.unit}".strip()


def collect(db: Session, period: str) -> dict:
    tz = hospital_tz(db)
    ym = lambda d: d.astimezone(tz).strftime("%Y-%m")
    periods = [p for p in completed_periods(13) if p <= period][-12:]
    if period not in periods:
        periods = (periods + [period])[-12:]
    inds = db.scalars(select(Indicator).order_by(Indicator.position)).all()
    kpis, charts = [], []
    for ind in inds:
        pts = series(db, ind, periods)
        cur = next((p for p in pts if p["period"] == period), None)
        kpis.append({"ind": ind, "value": cur["value"] if cur else None, "rag": rag(ind, cur["value"] if cur else None)})
        if len(pts) >= 4:
            charts.append({"ind": ind, "pts": pts, "chart": run_chart(pts)})
    themes = Counter(t for f in db.scalars(select(FeedbackResponse).where(FeedbackResponse.sentiment != "positive")) if ym(f.created_at) == period for t in f.themes)
    incidents = [i for i in db.scalars(select(Incident)) if ym(i.occurred_at) == period]
    harm = Counter(i.harm for i in incidents)
    cats = Counter(i.category for i in incidents)
    users = {u.id: u.name for u in db.scalars(select(User))}
    overdue_capa = []
    for c, i in db.execute(select(Capa, Incident).join(Incident, Incident.id == Capa.incident_id).where(Capa.status != "Completed", Capa.due_at < now()).order_by(Capa.due_at)):
        overdue_capa.append({"incident": i.number, "action": c.action, "owner": users.get(c.owner_id, "Unassigned"), "due": c.due_at.astimezone(tz).strftime("%d %b %Y")})
    overdue_q = [{"incident": "Action", "action": a.text, "owner": users.get(a.owner_id, "Unassigned"), "due": a.due_at.astimezone(tz).strftime("%d %b %Y")}
                 for a in db.scalars(select(QualityAction).where(QualityAction.status != "Completed", QualityAction.due_at < now()).order_by(QualityAction.due_at))]
    tpls = {t.id: t for t in db.scalars(select(AuditTemplate))}
    runs = [r for r in db.scalars(select(AuditRun).where(AuditRun.status == "Completed", AuditRun.period == period))]
    audit_rows = []
    for tid, t in tpls.items():
        rs = [r for r in runs if r.template_id == tid]
        if rs:
            yes, no = sum(r.yes_count for r in rs), sum(r.no_count for r in rs)
            audit_rows.append({"name": t.name, "target": t.target, "score": round(100 * yes / (yes + no), 1), "audits": len(rs),
                               "lowest": min(rs, key=lambda r: r.score).unit + f" ({min(rs, key=lambda r: r.score).score:.0f}%)"})
    overdue_audits = [r for r in db.scalars(select(AuditRun).where(AuditRun.status != "Completed", AuditRun.due_at < now()))]
    chapters = [{"code": c.code, "name": c.name} | readiness(db, c.id) for c in db.scalars(select(StandardChapter).order_by(StandardChapter.position))]
    t = db.get(Tenant, "t1")
    return {"hospital": t.name, "branding": t.branding or {}, "period": period, "kpis": kpis, "charts": charts, "themes": themes.most_common(6), "harm": harm, "cats": cats,
            "incident_total": len(incidents), "serious": [i for i in incidents if i.sentinel], "overdue_actions": overdue_capa + overdue_q, "audits": audit_rows,
            "overdue_audits": len(overdue_audits), "readiness": readiness(db), "chapters": chapters, "survey_date": None}


def _logo(branding: dict):
    url = branding.get("logo_url") or ""
    m = re.match(r"data:image/(png|jpeg|jpg);base64,(.+)", url)
    if not m:
        return None
    try:
        img = Image(io.BytesIO(base64.b64decode(m.group(2))))
        ratio = min(40 * mm / img.imageWidth, 18 * mm / img.imageHeight)
        img.drawWidth, img.drawHeight, img.hAlign = img.imageWidth * ratio, img.imageHeight * ratio, "LEFT"
        return img
    except Exception:
        return None


def _mark(color):
    d = Drawing(46, 46)
    d.add(Rect(0, 0, 46, 46, rx=10, ry=10, fillColor=color, strokeColor=None))
    d.add(Rect(19, 9, 8, 28, fillColor=colors.white, strokeColor=None))
    d.add(Rect(9, 19, 28, 8, fillColor=colors.white, strokeColor=None))
    d.hAlign = "LEFT"
    return d


def _run_chart(c: dict, width=170 * mm, height=52 * mm) -> Drawing:
    ind, pts, med = c["ind"], c["pts"], c["chart"]["median"]
    d = Drawing(width, height)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 28, 16, width - 40, height - 24
    vals = [p["value"] for p in pts]
    lp.data = [[(i, v) for i, v in enumerate(vals)], [(0, med), (len(vals) - 1, med)], [(0, ind.target), (len(vals) - 1, ind.target)]]
    lo, hi = min(vals + [ind.target, med]), max(vals + [ind.target, med])
    pad = (hi - lo) * 0.15 or 1
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = lo - pad, hi + pad
    lp.yValueAxis.labels.fontSize = 6
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, len(vals) - 1
    lp.xValueAxis.valueSteps = list(range(len(vals)))
    lp.xValueAxis.labelTextFormat = lambda v: MONTHS[int(pts[int(v)]["period"][5:]) - 1][:3] if 0 <= int(v) < len(pts) else ""
    lp.xValueAxis.labels.fontSize = 6
    lp.lines[0].strokeColor, lp.lines[0].strokeWidth, lp.lines[0].symbol = colors.HexColor("#0f766e"), 1.6, None
    lp.lines[1].strokeColor, lp.lines[1].strokeDashArray, lp.lines[1].strokeWidth = colors.grey, (3, 2), 1
    lp.lines[2].strokeColor, lp.lines[2].strokeWidth = colors.HexColor("#0f9d6b"), 1
    d.add(lp)
    d.add(String(width - 10, height - 8, f"Median {med}  |  Target {ind.target}", fontSize=6, textAnchor="end", fillColor=colors.grey))
    return d


def _hbar(items: list[tuple[str, float]], width=170 * mm, height=50 * mm, color="#0f766e", maxv=None, label_w=95, cut=28) -> Drawing:
    d = Drawing(width, height)
    if not items:
        d.add(String(10, height / 2, "No data for this month", fontSize=8, fillColor=colors.grey))
        return d
    bc = HorizontalBarChart()
    bc.x, bc.y, bc.width, bc.height = label_w, 8, width - label_w - 15, height - 14
    bc.data = [[v for _, v in reversed(items)]]
    bc.categoryAxis.categoryNames = [k[:cut] for k, _ in reversed(items)]
    bc.categoryAxis.labels.fontSize, bc.valueAxis.labels.fontSize = 6.5, 6
    bc.valueAxis.valueMin, bc.valueAxis.valueMax = 0, maxv or max(v for _, v in items) * 1.15
    bc.bars[0].fillColor, bc.bars[0].strokeColor = colors.HexColor(color), None
    bc.barLabels.fontSize, bc.barLabelFormat, bc.barLabels.nudge = 6.5, "%d" if not maxv else "%.0f%%", 8
    bc.barLabels.boxAnchor = "w"
    d.add(bc)
    return d


def _vbar(items: list[tuple[str, float]], width=170 * mm, height=45 * mm) -> Drawing:
    d = Drawing(width, height)
    bc = VerticalBarChart()
    bc.x, bc.y, bc.width, bc.height = 20, 18, width - 30, height - 28
    bc.data = [[v for _, v in items]]
    bc.categoryAxis.categoryNames = [k for k, _ in items]
    bc.categoryAxis.labels.fontSize, bc.valueAxis.labels.fontSize = 7, 6
    bc.valueAxis.valueMin, bc.valueAxis.valueMax = 0, max(max(v for _, v in items), 1) * 1.2
    bc.valueAxis.valueStep = max(1, round(bc.valueAxis.valueMax / 5))
    bc.bars[0].fillColor, bc.bars[0].strokeColor = colors.HexColor("#0f766e"), None
    bc.barLabels.fontSize, bc.barLabelFormat, bc.barLabels.nudge = 7, "%d", 6
    d.add(bc)
    return d


def build_pdf(data: dict, cover_note: str, generated_by: str, survey: dict | None) -> bytes:
    brand = colors.HexColor(data["branding"].get("primary_color") or "#0f766e")
    base = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=base["Heading1"], textColor=brand, fontSize=17, spaceAfter=6)
    H2 = ParagraphStyle("H2", parent=base["Heading2"], textColor=brand, fontSize=12.5, spaceBefore=10, spaceAfter=4)
    B = ParagraphStyle("B", parent=base["BodyText"], fontSize=9, leading=12.5)
    SM = ParagraphStyle("SM", parent=B, fontSize=7.5, textColor=colors.grey)
    CELL = ParagraphStyle("CELL", parent=B, fontSize=8, leading=10)
    label = period_label(data["period"])
    story = [Spacer(1, 30 * mm), _logo(data["branding"]) or _mark(brand), Spacer(1, 10 * mm),
             Paragraph(data["hospital"], ParagraphStyle("hn", parent=B, fontSize=11, textColor=colors.grey)),
             Paragraph("Quality and Patient Safety Committee", ParagraphStyle("t1", parent=H1, fontSize=24, leading=28, textColor=colors.black)),
             Paragraph(f"Monthly pack · {label}", ParagraphStyle("t2", parent=H1, fontSize=15, leading=19)), Spacer(1, 12 * mm)]
    if cover_note.strip():
        story += [Paragraph("Note from the Quality Manager", H2)] + [Paragraph(p.replace("\n", "<br/>"), B) for p in cover_note.strip().split("\n\n")]
    story += [Spacer(1, 18 * mm), Paragraph(f"Prepared by {generated_by} on {date.today():%d %b %Y}. Figures are taken from the hospital's quality system at the time of export.", SM), PageBreak()]

    # KPIs vs target
    story += [Paragraph("1. Indicators against target", H1)]
    rows = [["Indicator", "Result", "Target", "Status"]]
    style = [("BACKGROUND", (0, 0), (-1, 0), brand), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f7")])]
    for n, k in enumerate(data["kpis"], 1):
        ind = k["ind"]
        rows.append([Paragraph(ind.name, CELL), Paragraph(fmt_value(ind, k["value"]), CELL), Paragraph(f"{'≤' if ind.direction == 'lower' else '≥'} {fmt_value(ind, ind.target)}", CELL), RAG_TEXT[k["rag"]]])
        style.append(("TEXTCOLOR", (3, n), (3, n), RAG[k["rag"]]))
        style.append(("FONTNAME", (3, n), (3, n), "Helvetica-Bold"))
    t = Table(rows, colWidths=[62 * mm, 42 * mm, 45 * mm, 25 * mm], repeatRows=1)
    t.setStyle(TableStyle(style))
    story += [t, Spacer(1, 4 * mm), Paragraph("Results are for the month shown. Definitions, numerators and denominators are in the indicator dictionary.", SM)]

    # run charts
    story += [Paragraph("2. Run charts", H1), Paragraph("Twelve completed months. Dashed line is the median; green line is the target. Six or more consecutive points on one side of the median is a shift.", B)]
    for c in data["charts"][:6]:
        ind, shift = c["ind"], c["chart"]["shift"]
        note = ""
        if shift:
            worse = (shift["side"] == "above") == (ind.direction == "lower")
            note = f' <font color="{"#dc4a3d" if worse else "#0f9d6b"}"><b>Shift: {shift["length"]} points {shift["side"]} the median ({"worsening" if worse else "improving"}).</b></font>'
        story.append(KeepTogether([Paragraph(f"<b>{ind.name}</b>{note}", B), _run_chart(c), Spacer(1, 3 * mm)]))

    # complaints and incidents
    story += [PageBreak(), Paragraph("3. Patient experience", H1), Paragraph(f"Top complaint themes in {label} (neutral and negative responses).", B), _hbar([(k, v) for k, v in data["themes"]])]
    story += [Paragraph("4. Incidents", H1), Paragraph(f"{data['incident_total']} incidents occurred in {label}. By harm level:", B)]
    harm_labels = dict(HARM_LEVELS)
    story += [_vbar([(harm_labels[k], data["harm"].get(k, 0)) for k, _ in HARM_LEVELS])]
    cat_labels = dict(INCIDENT_CATEGORIES)
    story += [Paragraph("By category:", B), _hbar([(cat_labels.get(k, k), v) for k, v in data["cats"].most_common()], height=42 * mm)]
    if data["serious"]:
        story += [Paragraph("Serious events", H2)] + [Paragraph(f"<b>{i.number}</b> · {i.title}. Status: {i.status}." + (" Escalated to management." if i.escalated_at else ""), B) for i in data["serious"]]
    else:
        story += [Paragraph("No serious events occurred this month.", B)]

    # actions
    story += [Paragraph("5. Overdue corrective actions", H1)]
    if data["overdue_actions"]:
        rows = [["Source", "Action", "Owner", "Was due"]] + [[a["incident"], Paragraph(a["action"][:220], CELL), Paragraph(a["owner"], CELL), a["due"]] for a in data["overdue_actions"][:14]]
        t = Table(rows, colWidths=[22 * mm, 100 * mm, 33 * mm, 20 * mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), brand), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [t]
    else:
        story += [Paragraph("No corrective actions are overdue.", B)]

    # audits
    story += [Paragraph("6. Audit compliance", H1)]
    if data["audits"]:
        rows = [["Audit", "Audits", "Compliance", "Target", "Lowest area"]]
        style = [("BACKGROUND", (0, 0), (-1, 0), brand), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]
        for n, a in enumerate(data["audits"], 1):
            rows.append([Paragraph(a["name"], CELL), a["audits"], f"{a['score']}%", f"{a['target']:.0f}%", a["lowest"]])
            style += [("TEXTCOLOR", (2, n), (2, n), RAG["green"] if a["score"] >= a["target"] else RAG["red"]), ("FONTNAME", (2, n), (2, n), "Helvetica-Bold")]
        t = Table(rows, colWidths=[60 * mm, 18 * mm, 28 * mm, 20 * mm, 48 * mm], repeatRows=1)
        t.setStyle(TableStyle(style))
        story += [t]
    else:
        story += [Paragraph("No audits were completed this month.", B)]
    story += [Paragraph(f"{data['overdue_audits']} scheduled audits are currently overdue.", SM)]

    # accreditation
    r = data["readiness"]
    story += [Paragraph("7. Accreditation readiness", H1),
              Paragraph(f"<b>{r['pct']}%</b> of applicable standard elements are met ({r['met']} of {r['applicable']})." + (f" Survey in {survey['days_left']} days ({survey['date']})." if survey else ""), B),
              _hbar([(f"{c['code']} {c['name']}", c["pct"]) for c in data["chapters"]], height=62 * mm, maxv=100, label_w=175, cut=44)]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 10 * mm, f"{data['hospital']} · Quality and Patient Safety Committee · {label}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(brand)
        canvas.setLineWidth(1.5)
        canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=16 * mm, title=f"Quality and Patient Safety Committee pack {label}",
                      author=data["hospital"]).build(story, onFirstPage=lambda c, d: None, onLaterPages=footer)
    return buf.getvalue()

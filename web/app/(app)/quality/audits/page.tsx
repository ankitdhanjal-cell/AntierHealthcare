"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, qs } from "@/lib/api";
import { ExportBar } from "@/components/ExportBar";
import { Badge, Empty, ErrorBox, PageHead, Pager, PctBar, Skeleton, fmtDate, fmtMonth, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

const axis = { fontSize: 11, fill: "var(--muted)" };
const thisMonth = () => new Date().toLocaleDateString("en-CA").slice(0, 7);

function Audits() {
  const me = useMe(); const toast = useToast(); const sp = useSearchParams();
  const tpls = useFetch<any[]>("/audits/templates");
  const meta = useFetch<any>(can(me, "incidents") || can(me, "incidents", "create") ? "/incidents/meta" : null);
  const [tid, setTid] = useState(""); const [f, setF] = useState<any>({ page: 1, size: 12, status: "", overdue: sp.get("overdue") || "", mine: "" });
  const [sched, setSched] = useState(false); const [units, setUnits] = useState<{ department_id: string; unit: string }[]>([]); const [u, setU] = useState({ department_id: "", unit: "" }); const [month, setMonth] = useState(thisMonth());
  const tplId = tid || tpls.data?.[0]?.id || "";
  const comp = useFetch<any>(tplId ? `/audits/compliance?template_id=${tplId}&months=6` : null, [tplId]);
  const runs = useFetch<any>("/audits/runs" + qs({ ...f, template_id: f.template_id || undefined }), [JSON.stringify(f)]);
  const set = (k: string, v: any) => setF({ ...f, [k]: v, page: 1 });
  if (tpls.loading) return <><PageHead title="Audits" /><Skeleton rows={5} /></>;
  if (tpls.error || !tpls.data) return <ErrorBox msg={tpls.error} retry={tpls.reload} />;
  const target = comp.data?.template.target;
  const line = comp.data?.overall.map((o: any) => ({ ...o, label: fmtMonth(o.period, true) })) || [];
  return (
    <>
      <PageHead title="Audits" sub="Infection control and clinical audits: schedule, record on the ward, and track compliance against target">
        <ExportBar filename="audits" rows={runs.data?.items} columns={[["Audit", (r) => r.template], ["Ward or area", (r) => r.unit || r.department], ["Month", (r) => r.period], ["Auditor", (r) => r.auditor], ["Status", (r) => (r.overdue ? "Overdue" : r.status)], ["Compliance %", (r) => r.score ?? ""], ["Target %", (r) => r.target]]} />
        {can(me, "audits", "admin") && <Link href="/quality/audits/templates" className="btn btn-ghost">Edit templates</Link>}
        {can(me, "audits", "approve") && <button className="btn" onClick={() => setSched(!sched)}>{sched ? "Close" : "Schedule audits"}</button>}
      </PageHead>
      {sched && <div className="card p-4 mb-4 text-sm space-y-3">
        <div className="font-medium">Schedule audits</div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 items-end">
          <div><label className="label" htmlFor="stpl">Template</label><select id="stpl" className="input" value={tplId} onChange={(e) => setTid(e.target.value)}>{tpls.data.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
          <div><label className="label" htmlFor="smon">Month</label><input id="smon" type="month" className="input" value={month} onChange={(e) => setMonth(e.target.value)} /></div>
          <div><label className="label" htmlFor="sdep">Department</label><select id="sdep" className="input" value={u.department_id} onChange={(e) => setU({ ...u, department_id: e.target.value })}><option value="">Choose…</option>{meta.data?.departments.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
          <div className="flex gap-2"><input className="input" aria-label="Ward or area" placeholder="Ward or area" value={u.unit} onChange={(e) => setU({ ...u, unit: e.target.value })} />
            <button className="btn btn-ghost" disabled={!u.department_id || !u.unit.trim()} onClick={() => { setUnits([...units, u]); setU({ department_id: u.department_id, unit: "" }); }}>Add</button></div></div>
        {units.length > 0 && <ul className="flex flex-wrap gap-2">{units.map((x, i) => <li key={i} className="px-2 py-1 rounded-full text-xs" style={{ background: "var(--line)" }}>{x.unit} <button aria-label={`Remove ${x.unit}`} className="ms-1" onClick={() => setUnits(units.filter((_, j) => j !== i))}>×</button></li>)}</ul>}
        <button className="btn" disabled={!units.length || !month} onClick={async () => { try { const r = await api("/audits/schedule", { body: { template_id: tplId, units, periods: [month] } }); toast(`${r.created} audits scheduled`); setUnits([]); runs.reload(); } catch (e: any) { toast(e.message, "err"); } }}>Schedule {units.length || ""} audit{units.length === 1 ? "" : "s"}</button>
      </div>}
      <div className="card p-4 mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2"><h2 className="font-medium text-sm">Compliance over time</h2>
          <select className="input !w-64" aria-label="Audit template" value={tplId} onChange={(e) => setTid(e.target.value)}>{tpls.data.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
        {comp.loading ? <Skeleton rows={3} /> : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div><ResponsiveContainer width="100%" height={230}>
              <LineChart data={line}><CartesianGrid strokeDasharray="3 3" stroke="#8884" /><XAxis dataKey="label" tick={axis} /><YAxis domain={[60, 100]} tick={axis} unit="%" />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} formatter={(v: any, _n: any, p: any) => [`${v}% (${p.payload.audits} audits)`, "Compliance"]} labelFormatter={(_: any, p: any) => (p?.[0] ? fmtMonth(p[0].payload.period) : "")} />
                <ReferenceLine y={target} stroke="#0f9d6b" strokeDasharray="5 4" label={{ value: `Target ${target}%`, position: "insideBottomRight", fill: "#0f9d6b", fontSize: 11 }} />
                <Line isAnimationActive={false} dataKey="score" stroke="#0f766e" strokeWidth={2} dot connectNulls /></LineChart></ResponsiveContainer></div>
            <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="th">Ward or area</th><th className="th w-40">Latest</th><th className="th">Change</th></tr></thead>
              <tbody>{comp.data?.units.map((x: any) => (
                <tr key={x.unit}><td className="td">{x.unit}</td>
                  <td className="td">{x.latest == null ? "—" : <div className="flex items-center gap-2"><div className="flex-1"><PctBar pct={x.latest} target={target} color={x.latest >= target ? "#0f9d6b" : "#dc4a3d"} /></div><span className="tabular-nums w-12 text-end">{x.latest}%</span></div>}</td>
                  <td className="td tabular-nums" style={{ color: x.change != null && x.change < -5 ? "#dc2626" : "var(--muted)" }}>{x.change == null ? "—" : `${x.change > 0 ? "+" : ""}${x.change} pts`}</td></tr>))}</tbody></table>
              {!comp.data?.units.length && <Empty title="No completed audits yet" hint="Completed audits appear here by ward." />}</div></div>)}
      </div>
      <div className="card p-3 mb-3 flex flex-wrap gap-2 items-center">
        <select className="input !w-60" aria-label="Template" value={f.template_id || ""} onChange={(e) => set("template_id", e.target.value)}><option value="">All audit types</option>{tpls.data.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
        <select className="input !w-40" aria-label="Status" value={f.status} onChange={(e) => set("status", e.target.value)}><option value="">Any status</option><option>Scheduled</option><option>Completed</option></select>
        <label className="text-sm flex items-center gap-1"><input type="checkbox" checked={!!f.overdue} onChange={(e) => set("overdue", e.target.checked ? "true" : "")} /> Overdue only</label>
        <label className="text-sm flex items-center gap-1"><input type="checkbox" checked={!!f.mine} onChange={(e) => set("mine", e.target.checked ? "true" : "")} /> Assigned to me</label>
      </div>
      <div className="card overflow-x-auto">
        {runs.loading ? <Skeleton /> : runs.error ? <ErrorBox msg={runs.error} retry={runs.reload} /> : runs.data.items.length === 0 ? <Empty title="No audits match" hint="Clear a filter, or schedule an audit." /> : (
          <table className="w-full"><thead><tr><th className="th">Audit</th><th className="th">Ward or area</th><th className="th">Month</th><th className="th">Auditor</th><th className="th">Status</th><th className="th">Compliance</th><th className="th"></th></tr></thead>
            <tbody>{runs.data.items.map((r: any) => (
              <tr key={r.id} className={r.overdue ? "bg-red-500/5" : ""}><td className="td">{r.template}</td><td className="td">{r.unit || r.department}</td><td className="td whitespace-nowrap">{fmtMonth(r.period)}</td><td className="td">{r.auditor}</td>
                <td className="td whitespace-nowrap">{r.overdue ? <Badge k="Overdue" /> : <Badge k={r.status} />}{r.overdue && <span className="block text-xs text-red-600">due {fmtDate(r.due_at)}</span>}</td>
                <td className="td tabular-nums">{r.score == null ? "—" : <span style={{ color: r.on_target ? "#0f9d6b" : "#dc2626", fontWeight: 600 }}>{r.score}%</span>}</td>
                <td className="td"><Link className="btn btn-ghost" href={`/quality/audits/runs/${r.id}`}>{r.status === "Completed" ? "View" : "Start"}</Link></td></tr>))}</tbody></table>)}
        {runs.data && <Pager page={f.page} size={f.size} total={runs.data.total} onPage={(p) => setF({ ...f, page: p })} />}
      </div>
    </>
  );
}

export default function Page() { return <Suspense><Audits /></Suspense>; }

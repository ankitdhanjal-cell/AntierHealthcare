"use client";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Empty, ErrorBox, PageHead, Skeleton, fmtMonth, useFetch } from "@/components/ui";
import { ExportBar } from "@/components/ExportBar";

const axis = { fontSize: 11, fill: "var(--muted)" };
const tone = (n: number | null) => (n == null ? "var(--muted)" : n >= 50 ? "#0f9d6b" : n >= 20 ? "#d97706" : "#dc4a3d");

function Table({ rows, label, keyName }: { rows: any[]; label: string; keyName: string }) {
  if (!rows.length) return <Empty title="Not enough responses yet" hint="Groups appear once they have at least five answers." />;
  return (
    <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">{label}</th><th className="th">NPS</th><th className="th">Promoters</th><th className="th">Passives</th><th className="th">Detractors</th><th className="th">Responses</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r[keyName]}><td className="td">{r[keyName]}</td><td className="td tabular-nums font-semibold" style={{ color: tone(r.nps) }}>{r.nps > 0 ? "+" : ""}{r.nps}</td>
        <td className="td tabular-nums">{r.promoters}</td><td className="td tabular-nums">{r.passives}</td><td className="td tabular-nums">{r.detractors}</td><td className="td tabular-nums">{r.count}</td></tr>)}</tbody></table></div>
  );
}

export default function Nps() {
  const { data, loading, error, reload } = useFetch<any>("/analytics/nps?months=6");
  if (loading) return <><PageHead title="Recommend score (NPS)" /><Skeleton rows={5} /></>;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  const o = data.overall;
  const trend = data.trend.map((t: any) => ({ ...t, label: fmtMonth(t.month, true) }));
  return (
    <>
      <PageHead title="Recommend score (NPS)" sub="How likely patients are to recommend the hospital, from 0 to 10. Promoters score 9-10, detractors 0-6.">
        <ExportBar filename="nps" rows={[...data.by_department.map((r: any) => ({ group: "Department", name: r.department, ...r })), ...data.by_doctor.map((r: any) => ({ group: "Attending doctor", name: r.doctor, ...r }))]}
          columns={[["Group", (r) => r.group], ["Name", (r) => r.name], ["NPS", (r) => r.nps], ["Promoters", (r) => r.promoters], ["Passives", (r) => r.passives], ["Detractors", (r) => r.detractors], ["Responses", (r) => r.count]]} /></PageHead>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
        <div className="card p-4"><div className="text-xs" style={{ color: "var(--muted)" }}>Net Promoter Score, last 6 months</div><div className="text-3xl font-semibold mt-1" style={{ color: tone(o.nps) }}>{o.nps == null ? "—" : `${o.nps > 0 ? "+" : ""}${o.nps}`}</div><div className="text-xs mt-1" style={{ color: "var(--muted)" }}>{o.count} responses</div></div>
        {[["Promoters (9-10)", o.promoters, "#0f9d6b"], ["Passives (7-8)", o.passives, "#94a3b8"], ["Detractors (0-6)", o.detractors, "#dc4a3d"]].map(([l, v, c]: any) => (
          <div key={l} className="card p-4"><div className="text-xs" style={{ color: "var(--muted)" }}>{l}</div><div className="text-2xl font-semibold mt-1 tabular-nums">{v}</div><div className="text-xs" style={{ color: c }}>{o.count ? Math.round((100 * v) / o.count) : 0}% of responses</div></div>))}
      </div>
      <div className="card p-4 mb-4"><h2 className="font-medium text-sm mb-2">NPS by month</h2>
        <ResponsiveContainer width="100%" height={220}><LineChart data={trend}><CartesianGrid strokeDasharray="3 3" stroke="#8884" /><XAxis dataKey="label" tick={axis} /><YAxis tick={axis} domain={[-20, 100]} /><ReferenceLine y={0} stroke="#8886" />
          <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} formatter={(v: any, _n: any, p: any) => [`${v} (${p.payload.count} responses)`, "NPS"]} labelFormatter={(_: any, p: any) => (p?.[0] ? fmtMonth(p[0].payload.month) : "")} />
          <Line isAnimationActive={false} dataKey="nps" stroke="#0f766e" strokeWidth={2} dot /></LineChart></ResponsiveContainer></div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card"><div className="p-4 pb-2"><h2 className="font-medium text-sm">By department</h2></div><Table rows={data.by_department} label="Department" keyName="department" /></div>
        <div className="card"><div className="p-4 pb-2"><h2 className="font-medium text-sm">By attending doctor</h2></div><Table rows={data.by_doctor} label="Attending doctor" keyName="doctor" /></div>
      </div>
    </>
  );
}

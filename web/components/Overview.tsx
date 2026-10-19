"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, ErrorBox, Skeleton, fmt, fmtDuration, fmtMonth, monthRange, useFetch } from "@/components/ui";
import { qs } from "@/lib/api";

const SENTIMENTS = [{ key: "positive", label: "Positive", color: "#0f9d6b" }, { key: "neutral", label: "Neutral", color: "#94a3b8" }, { key: "negative", label: "Negative", color: "#dc4a3d" }];
const axis = { fontSize: 11, fill: "var(--muted)" };

const kpiValue = (k: any) => k.key === "closure_time" ? fmtDuration(k.value) : k.key === "satisfaction" ? `${Number(Number(k.value).toFixed(1))} / 5` : k.value;
/** Whole percentages that add up to exactly 100 (largest remainder), so the legend never reads 101%. */
const pcts = (vals: number[]) => { const t = vals.reduce((a, b) => a + b, 0) || 1; const raw = vals.map((v) => (100 * v) / t); const f = raw.map(Math.floor); let left = 100 - f.reduce((a, b) => a + b, 0); raw.map((r, i) => [r - f[i], i]).sort((a: any, b: any) => b[0] - a[0]).forEach(([, i]: any) => { if (left-- > 0) f[i]++; }); return f; };
const kpiTarget = (k: any) => k.target == null ? null : k.key === "closure_time" ? fmtDuration(k.target) : k.key === "satisfaction" ? `${k.target} / 5` : k.target;

/** One-line tick so theme names such as "Doctor communication" never wrap or lose their space. */
const ThemeTick = ({ x, y, payload }: any) => <text x={x} y={y} dy={4} textAnchor="end" style={axis}>{payload.value}</text>;

export function Overview() {
  const { data, loading, error, reload } = useFetch<any>("/dashboard");
  const router = useRouter();
  const funnel = useFetch<any>("/analytics/funnel?months=6");
  const nps = useFetch<any>("/analytics/nps?months=6");
  const go = (path: string, params: Record<string, any>) => router.push(path + qs(params));
  if (loading) return <Skeleton rows={6} />;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  const total = SENTIMENTS.reduce((n, s) => n + (data.sentiment[s.key] || 0), 0) || 1;
  const P: Record<string, number> = Object.fromEntries(pcts(SENTIMENTS.map((x) => data.sentiment[x.key] || 0)).map((v, i) => [SENTIMENTS[i].key, v]));
  const trend = data.satisfaction_trend.map((d: any) => ({ ...d, label: fmtMonth(d.month, true) }));
  const casesTrend = data.cases_trend.map((d: any) => ({ ...d, label: fmtMonth(d.month, true) }));
  const tip = { contentStyle: { background: "var(--card)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }, labelStyle: { color: "var(--ink)" } };
  return (
    <>
      <div className="mb-3 mt-2"><h2 className="font-semibold">Patient experience</h2><p className="text-sm" style={{ color: "var(--muted)" }}>Last 6 months · {data.responses} feedback responses · click any figure to see the records</p></div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        {data.kpis.map((k: any) => (
          <Link key={k.key} href={k.href || "/"} className="card px-4 py-3 block transition-colors hover:border-[color:var(--line-strong)] hover:bg-black/[0.02]" aria-label={`${k.label}: open the records`} title={k.definition}>
            <div className="text-xs" style={{ color: "var(--muted)" }}>{k.label}</div>
            <div className="text-[26px] leading-8 font-semibold mt-0.5 tabular-nums">{kpiValue(k)}</div>
            <div className="mt-1 flex items-center gap-2 text-xs">{k.rag !== "neutral" && <Badge k={k.rag}>{k.rag === "green" ? "On target" : k.rag === "amber" ? "Watch" : "Off target"}</Badge>}{kpiTarget(k) != null && <span style={{ color: "var(--muted)" }}>Target {kpiTarget(k)}</span>}</div>
          </Link>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4"><h2 className="font-medium text-sm mb-2">Satisfaction trend <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· click a point</span></h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trend}><CartesianGrid strokeDasharray="3 3" stroke="#8884" /><XAxis dataKey="label" tick={axis} /><YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} tick={axis} />
              <Tooltip {...tip} formatter={(v: any, _n: any, p: any) => [`${v} / 5 (${p.payload.count} responses)`, "Average rating"]} labelFormatter={(_: any, p: any) => p?.[0] ? fmtMonth(p[0].payload.month) : ""} />
              <Line isAnimationActive={false} dataKey="rating" stroke="#0f766e" strokeWidth={2} dot={{ r: 4, cursor: "pointer", onClick: (_: any, e: any) => go("/feedback", monthRange(e.payload.month)) }} activeDot={{ r: 6, cursor: "pointer", onClick: (_: any, e: any) => go("/feedback", monthRange(e.payload.month)) }} /></LineChart></ResponsiveContainer></div>
        <div className="card p-4"><h2 className="font-medium text-sm mb-2">Cases opened and closed <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· click a bar</span></h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={casesTrend}><CartesianGrid strokeDasharray="3 3" stroke="#8884" /><XAxis dataKey="label" tick={axis} /><YAxis tick={axis} allowDecimals={false} />
              <Tooltip {...tip} labelFormatter={(_: any, p: any) => p?.[0] ? fmtMonth(p[0].payload.month) : ""} />
              <Bar isAnimationActive={false} name="Opened" dataKey="opened" fill="#dc4a3d" cursor="pointer" onClick={(d: any) => go("/cases", monthRange(d.month))} />
              <Bar isAnimationActive={false} name="Closed" dataKey="closed" fill="#0f766e" cursor="pointer" onClick={(d: any) => { const r = monthRange(d.month); go("/cases", { closed: true, closed_from: r.date_from, closed_to: r.date_to }); }} /></BarChart></ResponsiveContainer>
          <Legend2 items={[["Opened", "#dc4a3d"], ["Closed", "#0f766e"]]} /></div>
        <div className="card p-4"><h2 className="font-medium text-sm mb-2">Top complaint themes <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· click a bar</span></h2>
          {data.top_themes.length === 0 ? <p className="text-sm" style={{ color: "var(--muted)" }}>No complaint themes in this period.</p> :
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.top_themes} layout="vertical" margin={{ left: 8 }}><XAxis type="number" tick={axis} allowDecimals={false} /><YAxis type="category" dataKey="theme" width={150} tick={<ThemeTick />} />
                <Tooltip {...tip} cursor={{ fill: "#8882" }} />
                <Bar isAnimationActive={false} name="Responses" dataKey="count" fill="#0f766e" cursor="pointer" onClick={(d: any) => go("/feedback", { theme: d.theme, not_positive: true, date_from: data.since })} /></BarChart></ResponsiveContainer>}</div>
        <div className="card p-4"><h2 className="font-medium text-sm mb-3">Sentiment mix <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· click a row</span></h2>
          <div className="flex h-3 rounded-sm overflow-hidden mb-4" role="img" aria-label={SENTIMENTS.map((s) => `${s.label} ${P[s.key]}%`).join(", ")}>
            {SENTIMENTS.map((s) => <div key={s.key} style={{ width: `${100 * (data.sentiment[s.key] || 0) / total}%`, background: s.color }} />)}
          </div>
          <ul className="space-y-1">{SENTIMENTS.map((s) => (
            <li key={s.key}><Link href={"/feedback" + qs({ sentiment: s.key, date_from: data.since })} className="flex items-center gap-3 px-2 py-2 rounded-md hover:bg-black/5 text-sm">
              <span className="w-3 h-3 rounded-sm" style={{ background: s.color }} /><span className="flex-1">{s.label}</span>
              <span className="tabular-nums">{data.sentiment[s.key] || 0}</span><span className="w-12 text-end tabular-nums font-medium">{P[s.key]}%</span></Link></li>))}</ul></div>
      </div>
      {funnel.data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
          <div className="card p-4 lg:col-span-2">
            <div className="flex justify-between items-baseline mb-3"><h2 className="font-medium text-sm">Review funnel <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· last 6 months</span></h2><span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: "var(--line)", color: "var(--muted)" }}>Sample data</span></div>
            <ul className="space-y-1.5">{funnel.data.steps.map((s: any, n: number) => (
              <li key={s.label}><Link href={s.href} className="block hover:bg-black/5 rounded px-1 py-1">
                <div className="flex justify-between text-sm"><span>{s.label}</span><span className="tabular-nums"><b>{s.value.toLocaleString()}</b>{s.pct_of_previous != null && <span className="ms-2 text-xs" style={{ color: "var(--muted)" }}>{s.pct_of_previous}% of previous step</span>}</span></div>
                <div className="h-2 rounded-sm mt-1" style={{ background: "var(--line)" }}><div className="h-full" style={{ width: `${s.pct_of_sent ?? 0}%`, background: n === 0 ? "#64748b" : "var(--brand)" }} /></div></Link></li>))}</ul>
            <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Every satisfied patient is invited to review on Google. Patients who are unhappy get a thank-you and a call-back, and nothing stops them posting publicly.</p>
          </div>
          {nps.data && <Link href="/feedback/nps" className="card px-4 py-3 block transition-colors hover:border-[color:var(--line-strong)] hover:bg-black/[0.02]" title="Net Promoter Score: percent of patients scoring 9-10 minus percent scoring 0-6 on likelihood to recommend.">
            <h2 className="font-medium text-sm">Recommend score (NPS)</h2>
            <div className="text-4xl font-semibold mt-3 tabular-nums" style={{ color: nps.data.overall.nps >= 50 ? "#0f9d6b" : nps.data.overall.nps >= 20 ? "#d97706" : "#dc4a3d" }}>{nps.data.overall.nps == null ? "—" : `${nps.data.overall.nps > 0 ? "+" : ""}${nps.data.overall.nps}`}</div>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{nps.data.overall.count} responses · by department and doctor</p>
            <div className="flex h-2 rounded-sm overflow-hidden mt-3" role="img" aria-label="Promoters, passives and detractors">{[["promoters", "#0f9d6b"], ["passives", "#94a3b8"], ["detractors", "#dc4a3d"]].map(([k, c]) => <div key={k} style={{ width: `${nps.data.overall.count ? (100 * nps.data.overall[k]) / nps.data.overall.count : 0}%`, background: c }} />)}</div></Link>}
        </div>)}
      <div className="card mt-4">
        <div className="p-4 flex justify-between"><h2 className="font-medium text-sm">Overdue cases</h2><Link className="text-xs underline" href="/cases?overdue=true">View all</Link></div>
        {data.overdue_cases.length === 0 ? <p className="px-4 pb-4 text-sm" style={{ color: "var(--muted)" }}>No cases are past their SLA.</p> :
          data.overdue_cases.map((c: any) => <Link key={c.id} href={`/cases/${c.id}`} className="flex justify-between gap-3 td hover:bg-black/5"><span><Badge k="Overdue" /> <b className="ms-2">{c.number}</b> {c.title}</span><span className="whitespace-nowrap" style={{ color: "var(--muted)" }}>due {fmt(c.due_at)}</span></Link>)}
      </div>
    </>
  );
}

function Legend2({ items }: { items: [string, string][] }) {
  return <div className="flex gap-4 text-xs mt-1" style={{ color: "var(--muted)" }}>{items.map(([n, c]) => <span key={n} className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: c }} />{n}</span>)}</div>;
}

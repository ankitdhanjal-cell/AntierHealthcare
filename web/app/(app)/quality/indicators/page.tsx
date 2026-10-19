"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Empty, ErrorBox, PageHead, Skeleton, Spark, fmtMonth, useFetch } from "@/components/ui";
import { showValue, unitLabel } from "@/components/indicatorFormat";
import { can, useMe } from "@/components/Shell";
import { ExportBar } from "@/components/ExportBar";
import { IndicatorForm } from "@/components/IndicatorForm";

const axis = { fontSize: 11, fill: "var(--muted)" };

function Pareto({ source }: { source: string }) {
  const router = useRouter();
  const { data, loading, error, reload } = useFetch<any>(`/indicators/pareto?source=${source}&months=6`);
  if (loading) return <Skeleton rows={3} />;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  if (!data.items.length) return <Empty title="Nothing to chart yet" hint="Items appear here once there is data in the last six months." />;
  return (
    <div>
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={data.items} margin={{ right: 8 }}><CartesianGrid strokeDasharray="3 3" stroke="#8884" />
          <XAxis dataKey="label" tick={axis} interval={0} angle={-25} textAnchor="end" height={64} /><YAxis yAxisId="l" tick={axis} allowDecimals={false} /><YAxis yAxisId="r" orientation="right" domain={[0, 100]} tick={axis} unit="%" />
          <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} />
          <Bar yAxisId="l" isAnimationActive={false} name="Count" dataKey="count" fill="#0f766e" cursor="pointer" onClick={(d: any) => router.push(d.href)} />
          <Line yAxisId="r" isAnimationActive={false} name="Cumulative %" dataKey="cumulative" stroke="#dc4a3d" strokeWidth={2} dot /></ComposedChart></ResponsiveContainer>
      <p className="text-xs" style={{ color: "var(--muted)" }}>The vital few (about 80% of the total): <b>{data.vital_few.join(", ")}</b>. Click a bar to see the records.</p>
    </div>
  );
}

export default function Indicators() {
  const me = useMe();
  const { data, loading, error, reload } = useFetch<any[]>("/indicators?months=12");
  const [src, setSrc] = useState("themes"); const [adding, setAdding] = useState(false);
  if (loading) return <><PageHead title="Quality indicators" /><Skeleton rows={6} /></>;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  return (
    <>
      <PageHead title="Quality indicators" sub="Dictionary of definitions, numerators, denominators and targets, with the last 12 completed months">
        <ExportBar filename="quality-indicators" rows={data} columns={[["Indicator", (i) => i.name], ["Definition", (i) => i.definition], ["Numerator", (i) => i.numerator], ["Denominator", (i) => i.denominator], ["Latest", (i) => i.latest?.value ?? ""],
          ["Month", (i) => i.latest?.period ?? ""], ["Target", (i) => i.target], ["Direction", (i) => (i.direction === "lower" ? "lower is better" : "higher is better")], ["Source", (i) => i.source], ["Owner", (i) => i.owner]]} />
        {can(me, "indicators", "admin") && <button className="btn btn-ghost" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add indicator"}</button>}
        {can(me, "indicators", "create") && <Link href="/quality/indicators/entry" className="btn">Enter monthly values</Link>}
      </PageHead>
      {adding && <IndicatorForm onDone={() => { setAdding(false); reload(); }} onCancel={() => setAdding(false)} />}
      {!me.sees_all && <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>These figures cover the whole hospital, not only your department.</p>}
      <div className="card overflow-x-auto mb-4">
        <table className="w-full"><thead><tr><th className="th">Indicator</th><th className="th">Latest</th><th className="th">Target</th><th className="th">Status</th><th className="th">12-month trend</th><th className="th">Owner</th></tr></thead>
          <tbody>{data.map((i) => (
            <tr key={i.id}><td className="td min-w-[16rem]"><Link className="underline font-medium" href={`/quality/indicators/${i.id}`} title={i.definition}>{i.name}</Link>
              <span className="block text-xs" style={{ color: "var(--muted)" }}>{i.auto ? "Calculated from records" : "Entered monthly"} · {i.frequency}</span></td>
              <td className="td whitespace-nowrap tabular-nums font-semibold">{showValue(i, i.latest?.value)} <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>{unitLabel(i)}</span>{i.latest && <span className="block text-xs font-normal" style={{ color: "var(--muted)" }}>{fmtMonth(i.latest.period)}</span>}</td>
              <td className="td whitespace-nowrap tabular-nums">{i.direction === "lower" ? "≤" : "≥"} {showValue(i, i.target)}</td>
              <td className="td whitespace-nowrap">{i.rag === "neutral" ? "—" : <Badge k={i.rag}>{i.rag === "green" ? "On target" : i.rag === "amber" ? "Watch" : "Off target"}</Badge>}
                {i.shift_label && <span className="block text-xs mt-1" style={{ color: i.shift_label === "worsening" ? "#dc2626" : "#0f9d6b" }}>Shift: {i.shift_label}</span>}</td>
              <td className="td"><Spark values={i.spark} color={i.rag === "red" ? "#dc4a3d" : "var(--brand)"} /></td><td className="td">{i.owner}</td></tr>))}</tbody></table>
      </div>
      <div className="card p-4">
        <div className="flex flex-wrap justify-between items-center gap-2 mb-2"><h2 className="font-medium text-sm">Pareto chart: the vital few</h2>
          <div className="flex gap-2"><button className={`btn ${src === "themes" ? "" : "btn-ghost"}`} onClick={() => setSrc("themes")}>Complaint themes</button><button className={`btn ${src === "incident_categories" ? "" : "btn-ghost"}`} onClick={() => setSrc("incident_categories")}>Incident categories</button></div></div>
        <Pareto key={src} source={src} />
      </div>
    </>
  );
}

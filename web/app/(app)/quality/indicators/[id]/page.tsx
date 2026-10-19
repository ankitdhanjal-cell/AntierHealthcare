"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, ErrorBox, PageHead, Skeleton, fmtMonth, useFetch } from "@/components/ui";
import { can, useMe } from "@/components/Shell";
import { useState } from "react";
import { IndicatorForm } from "@/components/IndicatorForm";
import { showValue, unitLabel } from "@/components/indicatorFormat";

const axis = { fontSize: 11, fill: "var(--muted)" };

export default function IndicatorPage() {
  const { id } = useParams<{ id: string }>(); const me = useMe();
  const { data: i, loading, error, reload } = useFetch<any>(`/indicators/${id}?months=12`); const [editing, setEditing] = useState(false);
  if (loading && !i) return <Skeleton rows={6} />;
  if (error || !i) return <ErrorBox msg={error} retry={reload} />;
  const inShift = new Set<number>(i.shift?.indexes || []);
  const pts = i.series.map((p: any, n: number) => ({ ...p, label: fmtMonth(p.period, true), shift: inShift.has(n) }));
  const shiftColor = i.shift_label === "worsening" ? "#dc2626" : "#0f9d6b";
  const Dot = (p: any) => <circle key={p.index} cx={p.cx} cy={p.cy} r={p.payload.shift ? 6 : 4} fill={p.payload.shift ? shiftColor : "#0f766e"} stroke="var(--card)" strokeWidth={1.5} />;
  return (
    <>
      <PageHead title={i.name} sub={`${i.auto ? "Calculated from records" : "Entered monthly"} · ${i.frequency} · owner ${i.owner}`}>
        {i.rag !== "neutral" && <Badge k={i.rag}>{i.rag === "green" ? "On target" : i.rag === "amber" ? "Watch" : "Off target"}</Badge>}
        {can(me, "indicators", "admin") && <button className="btn btn-ghost" onClick={() => setEditing(!editing)}>{editing ? "Close editor" : "Edit definition"}</button>}
        {!i.auto && can(me, "indicators", "create") && <Link className="btn" href="/quality/indicators/entry">Enter monthly values</Link>}
      </PageHead>
      {editing && <IndicatorForm ind={i} onDone={() => { setEditing(false); reload(); }} onCancel={() => setEditing(false)} />}
      {i.shift && <div className="mb-4 p-3 rounded-lg text-sm" style={{ border: `1px solid ${shiftColor}66`, background: `${shiftColor}14` }}>
        <b>Shift detected.</b> The last {i.shift.length} points are all {i.shift.side} the median ({showValue(i, i.median)} {unitLabel(i)}), which is a {i.shift_label} trend and not normal variation.</div>}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 card p-4">
          <h2 className="font-medium text-sm mb-2">Run chart <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· solid line is the target, dashed line is the median</span></h2>
          {pts.length < 3 ? <p className="text-sm" style={{ color: "var(--muted)" }}>Not enough months of data yet for a run chart.</p> :
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={pts}><CartesianGrid strokeDasharray="3 3" stroke="#8884" /><XAxis dataKey="label" tick={axis} /><YAxis tick={axis} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} labelFormatter={(_: any, p: any) => (p?.[0] ? fmtMonth(p[0].payload.period) : "")}
                  formatter={(v: any, _n: any, p: any) => [`${showValue(i, v)} ${unitLabel(i)} (${p.payload.numerator} / ${p.payload.denominator})`, i.name]} />
                <ReferenceLine y={i.target} stroke="#0f9d6b" label={{ value: `Target ${showValue(i, i.target)}`, position: "insideTopRight", fill: "#0f9d6b", fontSize: 11 }} />
                <ReferenceLine y={i.median} stroke="var(--muted)" strokeDasharray="5 4" label={{ value: `Median ${showValue(i, i.median)}`, position: "insideBottomRight", fill: "var(--muted)", fontSize: 11 }} />
                <Line isAnimationActive={false} dataKey="value" stroke="#0f766e" strokeWidth={2} dot={<Dot />} /></LineChart></ResponsiveContainer>}
        </div>
        <div className="card p-4 text-sm space-y-3">
          <div className="font-medium">Definition</div>
          <p>{i.definition}</p>
          <div><span className="label">Numerator</span>{i.numerator}</div><div><span className="label">Denominator</span>{i.denominator}</div>
          <div><span className="label">Calculation</span>numerator ÷ denominator{i.multiplier !== 1 ? ` × ${i.multiplier.toLocaleString()}` : ""}{unitLabel(i) ? ` (${unitLabel(i)})` : ""}</div>
          <div><span className="label">Target</span>{i.direction === "lower" ? "At or below" : "At or above"} {showValue(i, i.target)} · watch from {showValue(i, i.amber)}</div>
          <div><span className="label">Data source</span>{i.source}</div>
          {i.drill && <Link className="underline" href={i.drill}>See the records</Link>}
        </div>
      </div>
      <div className="card overflow-x-auto mt-4">
        <table className="w-full"><thead><tr><th className="th">Month</th><th className="th">Numerator</th><th className="th">Denominator</th><th className="th">Value</th><th className="th">Note</th></tr></thead>
          <tbody>{[...i.series].reverse().map((p: any) => <tr key={p.period}><td className="td">{fmtMonth(p.period)}</td><td className="td tabular-nums">{p.numerator}</td><td className="td tabular-nums">{p.denominator}</td><td className="td tabular-nums font-medium">{showValue(i, p.value)} {unitLabel(i)}</td><td className="td">{p.note}</td></tr>)}</tbody></table>
      </div>
    </>
  );
}

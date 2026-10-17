"use client";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, ErrorBox, PageHead, Skeleton, fmt, useFetch } from "@/components/ui";

export default function Home() {
  const { data, loading, error, reload } = useFetch<any>("/dashboard");
  if (loading) return <><PageHead title="Quality Overview" /><Skeleton rows={6} /></>;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  const sent = [{ n: "Positive", v: data.sentiment.positive, c: "#0f9d6b" }, { n: "Neutral", v: data.sentiment.neutral, c: "#94a3b8" }, { n: "Negative", v: data.sentiment.negative, c: "#dc4a3d" }];
  return (
    <>
      <PageHead title="Quality Overview" sub={`Last 6 months · ${data.responses} feedback responses`} />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        {data.kpis.map((k: any) => (
          <div key={k.key} className="card p-4">
            <div className="text-xs" style={{ color: "var(--muted)" }}>{k.label}</div>
            <div className="text-2xl font-semibold mt-1">{k.value} <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>{k.unit}</span></div>
            <div className="mt-1 flex items-center gap-2 text-xs">{k.rag !== "neutral" && <Badge k={k.rag}>{k.rag === "green" ? "On target" : k.rag === "amber" ? "Watch" : "Off target"}</Badge>}{k.target != null && <span style={{ color: "var(--muted)" }}>Target {k.target}</span>}</div>
          </div>
        ))}
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card p-4"><h2 className="font-medium text-sm mb-2">Satisfaction trend</h2>
          <ResponsiveContainer width="100%" height={220}><LineChart data={data.satisfaction_trend}><CartesianGrid strokeDasharray="3 3" stroke="#8884" /><XAxis dataKey="month" fontSize={11} /><YAxis domain={[3, 5]} fontSize={11} /><Tooltip /><Line isAnimationActive={false} dataKey="rating" stroke="#0f766e" strokeWidth={2} dot /></LineChart></ResponsiveContainer></div>
        <div className="card p-4"><h2 className="font-medium text-sm mb-2">Cases opened vs closed</h2>
          <ResponsiveContainer width="100%" height={220}><BarChart data={data.cases_trend}><CartesianGrid strokeDasharray="3 3" stroke="#8884" /><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} allowDecimals={false} /><Tooltip /><Bar isAnimationActive={false} dataKey="opened" fill="#dc4a3d" /><Bar isAnimationActive={false} dataKey="closed" fill="#0f766e" /></BarChart></ResponsiveContainer></div>
        <div className="card p-4"><h2 className="font-medium text-sm mb-2">Top complaint themes</h2>
          <ResponsiveContainer width="100%" height={220}><BarChart data={data.top_themes} layout="vertical"><XAxis type="number" fontSize={11} /><YAxis type="category" dataKey="theme" width={130} fontSize={11} /><Tooltip /><Bar isAnimationActive={false} dataKey="count" fill="#0f766e" /></BarChart></ResponsiveContainer></div>
        <div className="card p-4"><h2 className="font-medium text-sm mb-2">Sentiment mix</h2>
          <ResponsiveContainer width="100%" height={220}><PieChart><Pie isAnimationActive={false} data={sent} dataKey="v" nameKey="n" innerRadius={50} outerRadius={85} label>{sent.map((s) => <Cell key={s.n} fill={s.c} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div>
      </div>
      <div className="card mt-4">
        <div className="p-4 flex justify-between"><h2 className="font-medium text-sm">Overdue cases</h2><Link className="text-xs underline" href="/cases?overdue=true">View all</Link></div>
        {data.overdue_cases.length === 0 ? <p className="px-4 pb-4 text-sm" style={{ color: "var(--muted)" }}>No cases are past their SLA.</p> :
          data.overdue_cases.map((c: any) => <Link key={c.id} href={`/cases/${c.id}`} className="flex justify-between td hover:bg-black/5"><span><Badge k="Overdue" /> <b className="ms-2">{c.number}</b> {c.title}</span><span style={{ color: "var(--muted)" }}>due {fmt(c.due_at)}</span></Link>)}
      </div>
    </>
  );
}

"use client";
import Link from "next/link";
import { Badge, ErrorBox, PageHead, PctBar, Skeleton, fmt, useFetch } from "@/components/ui";
import { Overview } from "@/components/Overview";
import { TasksPanel } from "@/components/TasksPanel";
import { showValue, unitLabel } from "@/components/indicatorFormat";

const rag = (p: number) => (p >= 85 ? "#0f9d6b" : p >= 65 ? "#d97706" : "#dc4a3d");

function Stat({ label, value, href, tone, hint }: { label: string; value: any; href: string; tone?: string; hint?: string }) {
  return (
    <Link href={href} className="card p-4 block hover:shadow-md transition-shadow" aria-label={`${label}: open the records`}>
      <div className="text-xs" style={{ color: "var(--muted)" }}>{label}</div>
      <div className="text-2xl font-semibold mt-1 tabular-nums" style={tone ? { color: tone } : {}}>{value}</div>
      {hint && <div className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{hint}</div>}
    </Link>
  );
}

function QualityHome({ h }: { h: any }) {
  const c = h.counts; const hot = (n: number) => (n > 0 ? "#dc2626" : undefined);
  return (
    <>
      <PageHead title="Quality Overview" sub="Accreditation readiness, overdue actions and what needs attention first" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <Stat label="Accreditation readiness" value={`${h.readiness.pct}%`} tone={rag(h.readiness.pct)} href="/quality/accreditation" hint={`${h.readiness.met} of ${h.readiness.applicable} elements met · ${h.gaps} open gaps`} />
        <Stat label="Survey countdown" value={h.days_left == null ? "Not set" : `${h.days_left} days`} href="/quality/accreditation" hint={h.survey_date ? `Survey ${new Date(h.survey_date).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}` : "Set the survey date"} />
        <Stat label="Overdue actions" value={c.overdue_actions} tone={hot(c.overdue_actions)} href="/quality/actions?overdue=true" hint="Corrective and accreditation actions" />
        <Stat label="Cases past SLA" value={c.cases_past_sla} tone={hot(c.cases_past_sla)} href="/cases?overdue=true" />
        <Stat label="Open incidents" value={c.open_incidents} href="/quality/incidents?open=true" hint={`${c.triage_queue} waiting for triage`} />
        <Stat label="Serious events open" value={c.serious_open} tone={hot(c.serious_open)} href="/quality/incidents?sentinel=true&open=true" />
        <Stat label="Incident investigations overdue" value={c.overdue_incidents} tone={hot(c.overdue_incidents)} href="/quality/incidents?overdue=true" />
        <Stat label="Audits overdue" value={c.overdue_audits} tone={hot(c.overdue_audits)} href="/quality/audits?overdue=true" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2 space-y-4 min-w-0">
          <div className="card p-4"><h2 className="font-medium text-sm mb-2">Indicators off target</h2>
            {h.off_target.length === 0 ? <p className="text-sm" style={{ color: "var(--muted)" }}>Every indicator is on target or on watch.</p> :
              <ul className="divide-y" style={{ borderColor: "var(--line)" }}>{h.off_target.map((i: any) => (
                <li key={i.id}><Link className="flex justify-between py-2 text-sm hover:bg-black/5" href={`/quality/indicators/${i.id}`}><span>{i.name}</span><span className="tabular-nums"><Badge k="red">Off target</Badge> <b className="ms-2">{showValue(i, i.value)} {unitLabel(i)}</b></span></Link></li>))}</ul>}
            <Link className="text-xs underline" href="/quality/indicators">All indicators</Link></div>
          {h.open_by_harm.length > 0 && <div className="card p-4"><h2 className="font-medium text-sm mb-3">Open incidents by harm level</h2>
            <div className="space-y-2">{h.open_by_harm.map((x: any) => (
              <Link key={x.harm} href={`/quality/incidents?open=true&harm=${x.harm}`} className="flex items-center gap-3 text-sm hover:bg-black/5 rounded px-1"><span className="w-24"><Badge k={x.harm}>{x.label}</Badge></span><div className="flex-1"><PctBar pct={(100 * x.count) / c.open_incidents} color={x.harm === "severe" ? "#dc2626" : "var(--brand)"} /></div><span className="w-6 text-end tabular-nums">{x.count}</span></Link>))}</div></div>}
        </div>
        <TasksPanel />
      </div>
      <Overview />
    </>
  );
}

function PatientRelationsHome({ h }: { h: any }) {
  const c = h.counts;
  return (
    <>
      <PageHead title="Today's cases" sub="Open complaints by due time, and the call-backs still to make" />
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-4">
        <Stat label="Opened today" value={c.new_today} href="/cases?open=true" />
        <Stat label="Due today" value={c.due_today} href="/cases?open=true" />
        <Stat label="Past SLA" value={c.overdue} tone={c.overdue ? "#dc2626" : undefined} href="/cases?overdue=true" />
        <Stat label="Awaiting call-back" value={c.awaiting_callback} tone={c.awaiting_callback ? "#d97706" : undefined} href="/cases?open=true" hint="No call logged yet" />
        <Stat label="Feedback today" value={c.feedback_today} href="/feedback" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2 card overflow-x-auto min-w-0"><div className="p-4 flex justify-between"><h2 className="font-medium text-sm">Open cases, due soonest</h2><Link className="text-xs underline" href="/cases?open=true">All {c.open} open cases</Link></div>
          {h.cases.length === 0 ? <p className="px-4 pb-4 text-sm" style={{ color: "var(--muted)" }}>No open cases. New complaints open a case automatically.</p> :
            <table className="w-full"><thead><tr><th className="th">Case</th><th className="th">Owner</th><th className="th">Call-back</th><th className="th">Due</th></tr></thead>
              <tbody>{h.cases.map((x: any) => <tr key={x.id} className={x.overdue ? "bg-red-500/5" : ""}><td className="td min-w-[16rem]"><Link className="underline font-medium" href={`/cases/${x.id}`}>{x.number}</Link> {x.title}<span className="ms-2"><Badge k={x.urgency} /></span></td><td className="td">{x.owner}</td>
                <td className="td">{x.callback_logged ? <Badge k="green">Logged</Badge> : <Badge k="amber">Not yet</Badge>}</td><td className="td whitespace-nowrap" style={x.overdue ? { color: "#dc2626", fontWeight: 600 } : {}}>{fmt(x.due_at)}</td></tr>)}</tbody></table>}</div>
        <TasksPanel />
      </div>
      <Overview />
    </>
  );
}

function DepartmentHome({ h }: { h: any }) {
  const c = h.counts;
  return (
    <>
      <PageHead title={h.scoped ? "Department overview" : "Overview"} sub={h.scoped ? h.departments.join(" · ") : "All departments"} />
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-4">
        <Stat label="Open cases" value={c.open_cases} href="/cases?open=true" />
        <Stat label="Cases past SLA" value={c.overdue_cases} tone={c.overdue_cases ? "#dc2626" : undefined} href="/cases?overdue=true" />
        {c.open_incidents != null && <Stat label="Open incidents" value={c.open_incidents} href="/quality/incidents?open=true" />}
        {c.audits_due != null && <Stat label="Audits to complete" value={c.audits_due} href="/quality/audits" />}
        <Stat label="Patient rating, 30 days" value={c.rating_30d ?? "—"} href="/feedback" hint={`${c.responses_30d} responses`} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4"><div className="lg:col-span-2 min-w-0"><Overview /></div><TasksPanel /></div>
    </>
  );
}

export default function Home() {
  const { data, loading, error, reload } = useFetch<any>("/home");
  if (loading) return <><PageHead title="Home" /><Skeleton rows={6} /></>;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  return data.kind === "quality" ? <QualityHome h={data} /> : data.kind === "patient_relations" ? <PatientRelationsHome h={data} /> : <DepartmentHome h={data} />;
}

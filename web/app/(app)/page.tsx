"use client";
import Link from "next/link";
import { Badge, Empty, ErrorBox, PageHead, PctBar, Skeleton, Spark, fmt, fmtDate, fmtMonth, useFetch } from "@/components/ui";
import { Overview } from "@/components/Overview";
import { TasksPanel } from "@/components/TasksPanel";
import { n1, showValue, unitLabel } from "@/components/indicatorFormat";

const rag = (p: number) => (p >= 85 ? "#0f9d6b" : p >= 65 ? "#d97706" : "#dc4a3d");

function Stat({ label, value, href, tone, hint }: { label: string; value: any; href: string; tone?: string; hint?: string }) {
  return (
    <Link href={href} className="card px-4 py-3 block transition-colors hover:border-[color:var(--line-strong)] hover:bg-black/[0.02]" aria-label={`${label}: open the records`}>
      <div className="text-xs" style={{ color: "var(--muted)" }}>{label}</div>
      <div className="text-[26px] leading-8 font-semibold mt-0.5 tabular-nums" style={tone ? { color: tone } : {}}>{value}</div>
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
        <Stat label="Overdue actions" value={c.overdue_actions} tone={hot(c.overdue_actions)} href={h.links.overdue_actions} hint="Corrective and accreditation actions" />
        <Stat label="Cases past SLA" value={c.cases_past_sla} tone={hot(c.cases_past_sla)} href={h.links.cases_past_sla} />
        <Stat label="Open incidents" value={c.open_incidents} href={h.links.open_incidents} hint={`${c.triage_queue} waiting for triage`} />
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
        <Stat label="Opened today" value={c.new_today} href={h.links.new_today} />
        <Stat label="Due today" value={c.due_today} href={h.links.due_today} />
        <Stat label="Past SLA" value={c.overdue} tone={c.overdue ? "#dc2626" : undefined} href="/cases?overdue=true" />
        <Stat label="Awaiting call-back" value={c.awaiting_callback} tone={c.awaiting_callback ? "#d97706" : undefined} href={h.links.awaiting_callback} hint="No call logged yet" />
        <Stat label="Feedback today" value={c.feedback_today} href={h.links.feedback_today} />
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
        {c.audits_due != null && <Stat label="Audits to complete" value={c.audits_due} href={h.links.audits_due} />}
        {h.can_dashboard && <Stat label="Patient rating, 30 days" value={c.rating_30d ?? "—"} href={h.links.rating_30d} hint={c.responses_30d < 10 ? `${c.responses_30d} responses, too few for a trend` : `${c.responses_30d} responses`} />}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4"><div className="lg:col-span-2 min-w-0">{h.can_dashboard ? <Overview /> : null}</div><TasksPanel /></div>
    </>
  );
}

function Rag({ r }: { r: string }) {
  return r === "neutral" ? <span>—</span> : <Badge k={r}>{r === "green" ? "On target" : r === "amber" ? "Watch" : "Off target"}</Badge>;
}

function IndicatorTable({ rows }: { rows: any[] }) {
  return (
    <table className="w-full"><thead><tr><th className="th">Indicator</th><th className="th">Latest</th><th className="th">Target</th><th className="th">Status</th><th className="th">Trend</th></tr></thead>
      <tbody>{rows.map((i: any) => <tr key={i.id}><td className="td"><Link className="underline" href={`/quality/indicators/${i.id}`}>{i.name}</Link></td><td className="td tabular-nums">{showValue(i, i.value)} {unitLabel(i)}</td>
        <td className="td tabular-nums">{i.direction === "lower" ? "≤" : "≥"} {showValue(i, i.target)}</td><td className="td"><Rag r={i.rag} /></td><td className="td"><Spark values={i.spark} color={i.rag === "red" ? "#dc4a3d" : "var(--brand)"} /></td></tr>)}</tbody></table>
  );
}

function ManagementHome({ h }: { h: any }) {
  const sat = h.satisfaction;
  return (
    <>
      <PageHead title="Management summary" sub="Readiness, serious events, indicators against target and the patient trend, on one page">
        <Link href="/quality/reports" className="btn">Committee reports</Link>
      </PageHead>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <Stat label="Accreditation readiness" value={`${h.readiness.pct}%`} tone={rag(h.readiness.pct)} href="/quality/accreditation" hint={`${h.readiness.met} of ${h.readiness.applicable} elements met`} />
        <Stat label="Survey countdown" value={h.days_left == null ? "Not set" : `${h.days_left} days`} href="/quality/accreditation" />
        <Stat label="Serious events open" value={h.serious.length} tone={h.serious.length ? "#dc2626" : undefined} href="/quality/incidents?sentinel=true&open=true" />
        <Stat label="Indicators on target" value={`${h.on_target} of ${h.indicators.length}`} href="/quality/indicators" hint={`${h.watch} on watch, ${h.off_target} off target`} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 card overflow-x-auto min-w-0"><div className="p-4 flex justify-between"><h2 className="font-medium text-sm">Indicators against target</h2><Link className="text-xs underline" href="/quality/indicators">All indicators</Link></div><IndicatorTable rows={h.indicators} /></div>
        <div className="space-y-4 min-w-0">
          <div className="card p-4"><h2 className="font-medium text-sm mb-2">Serious events</h2>
            {h.serious.length === 0 ? <p className="text-sm" style={{ color: "var(--muted)" }}>No serious events are open.</p> : h.serious.map((i: any) => <Link key={i.id} href={`/quality/incidents/${i.id}`} className="block text-sm py-1 hover:bg-black/5"><b>{i.number}</b> {i.title}<span className="block text-xs" style={{ color: "var(--muted)" }}>{i.status} · {i.escalated ? "escalated to management" : "not yet escalated"}</span></Link>)}</div>
          {sat && <div className="card p-4"><h2 className="font-medium text-sm">Patient satisfaction</h2><div className="text-3xl font-semibold mt-2 tabular-nums">{showValue(sat, sat.value)} <span className="text-sm font-normal" style={{ color: "var(--muted)" }}>/ 5</span></div><div className="mt-2"><Spark values={sat.spark} /></div><p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Last 12 completed months</p></div>}
          <TasksPanel />
        </div>
      </div>
    </>
  );
}

function AuditHome({ h }: { h: any }) {
  const c = h.counts;
  return (
    <>
      <PageHead title="Infection control overview" sub={h.departments.length ? h.departments.join(" · ") : "All departments"} />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <Stat label="Audits to complete" value={c.due} href={h.links.due} />
        <Stat label="Audits overdue" value={c.overdue} tone={c.overdue ? "#dc2626" : undefined} href={h.links.overdue} />
        <Stat label="Below target (latest month)" value={c.below_target} tone={c.below_target ? "#d97706" : undefined} href="/quality/audits" />
        <Stat label="Completed audits" value={c.completed} href="/quality/audits?status=Completed" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4 min-w-0">
          <div className="card overflow-x-auto"><div className="p-4"><h2 className="font-medium text-sm">Compliance against target, latest month</h2></div>
            <table className="w-full"><thead><tr><th className="th">Audit</th><th className="th">Month</th><th className="th w-56">Compliance</th></tr></thead>
              <tbody>{h.compliance.map((x: any) => <tr key={x.id}><td className="td">{x.name}</td><td className="td">{fmtMonth(x.period)}</td>
                <td className="td"><div className="flex items-center gap-2"><div className="flex-1"><PctBar pct={x.score} target={x.target} color={x.score >= x.target ? "#0f9d6b" : "#dc4a3d"} /></div><span className="w-14 text-end tabular-nums">{n1(x.score)}%</span></div></td></tr>)}</tbody></table></div>
          <div className="card overflow-x-auto"><div className="p-4"><h2 className="font-medium text-sm">Infection indicators</h2></div><IndicatorTable rows={h.indicators} /></div>
          <div className="card"><div className="p-4 flex justify-between"><h2 className="font-medium text-sm">Next audits</h2><Link className="text-xs underline" href="/quality/audits">All audits</Link></div>
            {h.next.length === 0 ? <p className="px-4 pb-4 text-sm" style={{ color: "var(--muted)" }}>No audits are waiting.</p> : h.next.map((r: any) => <Link key={r.id} href={`/quality/audits/runs/${r.id}`} className="flex justify-between gap-3 td hover:bg-black/5"><span>{r.template} · {r.unit} · {r.period}</span><span className="whitespace-nowrap" style={{ color: r.overdue ? "#dc2626" : "var(--muted)" }}>{r.overdue ? "Overdue, " : "due "}{fmtDate(r.due_at)}</span></Link>)}</div>
        </div>
        <TasksPanel />
      </div>
    </>
  );
}

function ReporterHome({ h }: { h: any }) {
  const c = h.counts;
  return (
    <>
      <PageHead title="My reports" sub="Incidents you have reported and where each one stands. Reports are used to improve safety, not to blame people.">
        <Link href="/quality/incidents/new" className="btn">Report an incident</Link>
      </PageHead>
      <div className="grid grid-cols-3 gap-4 mb-4 max-w-2xl">
        <Stat label="Reported by me" value={c.total} href="/quality/incidents" />
        <Stat label="Still open" value={c.open} href="/quality/incidents?open=true" />
        <Stat label="Closed" value={c.closed} href="/quality/incidents?status=Closed" />
      </div>
      <div className="card overflow-x-auto max-w-4xl">
        {h.reports.length === 0 ? <Empty title="You have not reported an incident yet" hint="If something went wrong or almost did, report it. It takes about a minute." action={<Link href="/quality/incidents/new" className="btn">Report an incident</Link>} /> : (
          <table className="w-full"><thead><tr><th className="th">Report</th><th className="th">Reported</th><th className="th">Harm</th><th className="th">Where it stands</th></tr></thead>
            <tbody>{h.reports.map((r: any) => <tr key={r.id}><td className="td"><Link className="underline font-medium" href={`/quality/incidents/${r.id}`}>{r.number}</Link> {r.title}</td><td className="td whitespace-nowrap">{fmtDate(r.created_at)}</td><td className="td"><Badge k={r.harm}>{r.harm.replace("_", " ")}</Badge></td><td className="td"><Badge k={r.status} /></td></tr>)}</tbody></table>)}
      </div>
    </>
  );
}

export default function Home() {
  const { data, loading, error, reload } = useFetch<any>("/home");
  if (loading) return <><PageHead title="Home" /><Skeleton rows={6} /></>;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  return data.kind === "quality" ? <QualityHome h={data} /> : data.kind === "management" ? <ManagementHome h={data} /> : data.kind === "audit" ? <AuditHome h={data} /> : data.kind === "reporter" ? <ReporterHome h={data} /> : data.kind === "patient_relations" ? <PatientRelationsHome h={data} /> : <DepartmentHome h={data} />;
}

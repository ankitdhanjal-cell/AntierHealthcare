"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { fetchAllPages, qs } from "@/lib/api";
import { ExportBar } from "@/components/ExportBar";
import { Badge, Empty, ErrorBox, FilterChips, PageHead, Pager, Skeleton, fmt, useFetch } from "@/components/ui";
import { can, useMe } from "@/components/Shell";

const FILTERS = ["status", "harm", "category", "department_id", "sentinel", "overdue", "open", "mine", "q"];
const LABELS: Record<string, string> = { status: "Status", harm: "Harm", category: "Category", department_id: "Department", sentinel: "Serious events", overdue: "Past deadline", open: "Open", mine: "Mine", q: "Search" };
const BASE = { page: 1, size: 15, sort: "created_at", order: "desc" };

function Incidents() {
  const sp = useSearchParams(); const me = useMe();
  const [f, setF] = useState<any>(() => ({ ...BASE, ...Object.fromEntries(FILTERS.filter((k) => sp.get(k)).map((k) => [k, sp.get(k)])) }));
  const meta = useFetch<any>("/incidents/meta");
  const { data, loading, error, reload } = useFetch<any>("/incidents" + qs(f), [JSON.stringify(f)]);
  const queue = useFetch<any>(can(me, "incidents", "approve") ? "/incidents?size=1&status=Reported" : null);
  const set = (k: string, v: any) => setF({ ...f, [k]: v, page: 1 });
  const sort = (k: string) => setF({ ...f, sort: k, order: f.sort === k && f.order === "desc" ? "asc" : "desc" });
  const Th = ({ k, children }: any) => <th className="th cursor-pointer select-none" onClick={() => sort(k)}>{children}{f.sort === k ? (f.order === "desc" ? " ↓" : " ↑") : ""}</th>;
  const active = FILTERS.filter((k) => f[k]).map((k): [string, string] => [LABELS[k], ["sentinel", "overdue", "open", "mine"].includes(k) ? "yes" : String(f[k])]);
  const tab = (label: string, on: boolean, patch: any) => <button className={`btn ${on ? "" : "btn-ghost"}`} onClick={() => setF({ ...BASE, ...patch })}>{label}</button>;
  return (
    <>
      <PageHead title="Incidents" sub="Patient-safety events: report, triage, investigate and close with corrective actions">
        <ExportBar filename="incidents" fetchAll={() => fetchAllPages("/incidents", f)} columns={[["Incident", (i) => i.number], ["Summary", (i) => i.title], ["Category", (i) => i.category_label], ["Harm level", (i) => i.harm_label], ["Department", (i) => i.department],
          ["Location", (i) => i.location], ["Status", (i) => i.status], ["Serious event", (i) => (i.sentinel ? "Yes" : "No")], ["Investigator", (i) => i.investigator], ["Occurred", (i) => fmt(i.occurred_at)], ["Due", (i) => fmt(i.due_at)]]} />
        {can(me, "incidents", "create") && <Link href="/quality/incidents/new" className="btn">Report an incident</Link>}
      </PageHead>
      <div className="flex flex-wrap gap-2 mb-3">
        {tab("All", !f.status && !f.open && !f.overdue && !f.sentinel && !f.mine, {})}
        {can(me, "incidents", "approve") && tab(`Triage queue${queue.data ? ` (${queue.data.total})` : ""}`, f.status === "Reported", { status: "Reported" })}
        {tab("Open", !!f.open, { open: "true" })}
        {tab("Serious events", !!f.sentinel, { sentinel: "true" })}
        {tab("Past deadline", !!f.overdue, { overdue: "true" })}
        {tab("Reported or assigned to me", !!f.mine, { mine: "true" })}
      </div>
      <FilterChips items={active} onClear={() => setF(BASE)} />
      <div className="card p-3 mb-4 grid grid-cols-2 md:grid-cols-5 gap-2">
        <input className="input" placeholder="Search incidents…" value={f.q || ""} onChange={(e) => set("q", e.target.value)} aria-label="Search" />
        <select className="input" value={f.category || ""} onChange={(e) => set("category", e.target.value)} aria-label="Category"><option value="">Any category</option>{meta.data?.categories.map((c: any) => <option key={c.key} value={c.key}>{c.label}</option>)}</select>
        <select className="input" value={f.harm || ""} onChange={(e) => set("harm", e.target.value)} aria-label="Harm level"><option value="">Any harm level</option>{meta.data?.harms.map((c: any) => <option key={c.key} value={c.key}>{c.label}</option>)}</select>
        <select className="input" value={f.status || ""} onChange={(e) => set("status", e.target.value)} aria-label="Status"><option value="">Any status</option>{meta.data?.statuses.map((s: string) => <option key={s}>{s}</option>)}</select>
        <select className="input" value={f.department_id || ""} onChange={(e) => set("department_id", e.target.value)} aria-label="Department"><option value="">All departments</option>{meta.data?.departments.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
      </div>
      <div className="card overflow-x-auto">
        {loading ? <Skeleton /> : error ? <ErrorBox msg={error} retry={reload} /> : data.items.length === 0 ?
          <Empty title="No incidents match these filters" hint="Clear a filter, or report a new incident." action={can(me, "incidents", "create") ? <Link href="/quality/incidents/new" className="btn">Report an incident</Link> : undefined} /> : (
          <table className="w-full"><thead><tr><Th k="number">Incident</Th><th className="th">Summary</th><Th k="harm">Harm</Th><th className="th">Where</th><Th k="status">Status</Th><th className="th">Investigator</th><Th k="due_at">Due</Th></tr></thead>
            <tbody>{data.items.map((i: any) => (
              <tr key={i.id} className={i.sentinel ? "bg-red-500/5" : i.overdue ? "bg-red-500/[0.03]" : ""}>
                <td className="td whitespace-nowrap"><Link className="underline font-medium" href={`/quality/incidents/${i.id}`}>{i.number}</Link>{i.sentinel && <span className="ms-1"><Badge k="Sentinel">Serious event</Badge></span>}</td>
                <td className="td min-w-[14rem]">{i.title}<span className="block text-xs" style={{ color: "var(--muted)" }}>{i.category_label}</span></td>
                <td className="td"><Badge k={i.harm}>{i.harm_label}</Badge></td><td className="td whitespace-nowrap">{i.department}{i.location ? <span className="block text-xs" style={{ color: "var(--muted)" }}>{i.location}</span> : null}</td>
                <td className="td whitespace-nowrap"><Badge k={i.status} />{i.overdue && <span className="ms-1"><Badge k="Overdue" /></span>}</td>
                <td className="td">{i.investigator}</td><td className="td whitespace-nowrap" style={i.overdue ? { color: "#dc2626", fontWeight: 600 } : {}}>{i.status === "Closed" ? "—" : fmt(i.due_at)}</td>
              </tr>))}</tbody></table>
        )}
        {data && <Pager page={f.page} size={f.size} total={data.total} onPage={(p) => setF({ ...f, page: p })} />}
      </div>
    </>
  );
}
export default function Page() { return <Suspense><Incidents /></Suspense>; }

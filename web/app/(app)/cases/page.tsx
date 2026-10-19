"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, fetchAllPages, qs } from "@/lib/api";
import { ExportBar } from "@/components/ExportBar";
import { Badge, Empty, ErrorBox, FilterChips, PageHead, Pager, Skeleton, fmt, useFetch } from "@/components/ui";
import { useConfirm, useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

const FILTERS = ["status", "urgency", "overdue", "open", "closed", "loop", "no_call", "due_from", "due_to", "date_from", "date_to", "closed_from", "closed_to"];
const LABELS: Record<string, string> = { status: "Status", urgency: "Urgency", overdue: "Past SLA", open: "Open cases", closed: "Closed cases", loop: "Call-back loop", no_call: "No call-back yet", due_from: "Due from", due_to: "Due to", date_from: "Opened from", date_to: "Opened to", closed_from: "Closed from", closed_to: "Closed to" };

function Cases() {
  const sp = useSearchParams(); const me = useMe(); const toast = useToast(); const confirm = useConfirm();
  const [f, setF] = useState<any>(() => ({ page: 1, size: 15, sort: "created_at", order: "desc", ...Object.fromEntries(FILTERS.filter((k) => sp.get(k)).map((k) => [k, sp.get(k)])) }));
  const [sel, setSel] = useState<string[]>([]);
  const [owner, setOwner] = useState("");
  const users = useFetch<any[]>(can(me, "cases", "approve") ? "/cases/meta/assignees" : null);
  const { data, loading, error, reload } = useFetch<any>("/cases" + qs(f), [JSON.stringify(f)]);
  const set = (k: string, v: any) => setF({ ...f, [k]: v, page: 1 });
  const sort = (k: string) => setF({ ...f, sort: k, order: f.sort === k && f.order === "desc" ? "asc" : "desc" });
  const active = FILTERS.filter((k) => f[k]).map((k): [string, string] => [LABELS[k], ["overdue", "open", "closed", "no_call"].includes(k) ? "yes" : String(f[k])]);
  const Th = ({ k, children }: any) => <th className="th cursor-pointer" onClick={() => sort(k)}>{children}{f.sort === k ? (f.order === "desc" ? " ↓" : " ↑") : ""}</th>;
  const bulkAssign = async () => { await api("/cases/bulk", { body: { ids: sel, owner_id: owner } }); toast(`${sel.length} cases assigned`); setSel([]); reload(); };
  const bulkClose = async () => {
    if (!(await confirm({ title: `Close ${sel.length} cases?`, body: "They will be marked Closed with a bulk-closure note.", label: "Close cases", danger: true }))) return;
    await api("/cases/bulk", { body: { ids: sel, close: true, resolution: "Closed in bulk by Quality team." } }); toast("Cases closed"); setSel([]); reload();
  };
  return (
    <>
      <PageHead title="Cases" sub="Complaints from patient feedback, tracked against SLA">
        <ExportBar filename="cases" fetchAll={() => fetchAllPages("/cases", f)} columns={[["Case", (c) => c.number], ["Title", (c) => c.title], ["Department", (c) => c.department], ["Urgency", (c) => c.urgency], ["Status", (c) => c.status], ["Owner", (c) => c.owner],
          ["Opened", (c) => fmt(c.created_at)], ["Due", (c) => fmt(c.due_at)], ["Closed", (c) => fmt(c.closed_at)], ["Patient called back", (c) => (c.loop_closed ? "Yes" : "No")]]} /></PageHead>
      <FilterChips items={active} onClear={() => setF({ page: 1, size: 15, sort: "created_at", order: "desc" })} />
      <div className="card p-3 mb-4 flex flex-wrap gap-2 items-center">
        <input className="input !w-56" placeholder="Search number or title…" onChange={(e) => set("q", e.target.value)} />
        <select className="input !w-40" value={f.status || ""} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{["New", "Assigned", "In investigation", "Resolved", "Closed"].map((s) => <option key={s}>{s}</option>)}</select>
        <select className="input !w-44" aria-label="Call-back loop" value={f.loop || ""} onChange={(e) => set("loop", e.target.value)}><option value="">Any call-back state</option><option value="closed">Loop closed</option><option value="open">Loop still open</option></select>
        <select className="input !w-36" value={f.urgency || ""} onChange={(e) => set("urgency", e.target.value)}><option value="">Any urgency</option><option>high</option><option>medium</option><option>low</option></select>
        <label className="text-sm flex items-center gap-1"><input type="checkbox" checked={!!f.overdue} onChange={(e) => set("overdue", e.target.checked ? "true" : "")} /> Overdue only</label>
        {sel.length > 0 && can(me, "cases", "approve") && <div className="ms-auto flex gap-2 items-center">
          <select className="input !w-48" value={owner} onChange={(e) => setOwner(e.target.value)}><option value="">Assign to…</option>{users.data?.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.role})</option>)}</select>
          <button className="btn btn-ghost" disabled={!owner} onClick={bulkAssign}>Assign {sel.length}</button><button className="btn btn-danger" onClick={bulkClose}>Close {sel.length}</button></div>}
      </div>
      <div className="card overflow-x-auto">
        {loading ? <Skeleton /> : error ? <ErrorBox msg={error} retry={reload} /> : data.items.length === 0 ? <Empty title="No cases found" hint="Cases open automatically when a patient's feedback is not a happy one." /> :
          <table className="w-full"><thead><tr><th className="th w-8"></th><Th k="number">Case</Th><th className="th">Title</th><th className="th">Dept</th><Th k="urgency">Urgency</Th><Th k="status">Status</Th><th className="th">Owner</th><Th k="due_at">Due</Th></tr></thead>
            <tbody>{data.items.map((c: any) => (
              <tr key={c.id} className={c.overdue ? "bg-red-500/5" : ""}>
                <td className="td"><input type="checkbox" aria-label="Select case" checked={sel.includes(c.id)} onChange={(e) => setSel(e.target.checked ? [...sel, c.id] : sel.filter((x) => x !== c.id))} /></td>
                <td className="td whitespace-nowrap"><Link className="underline font-medium" href={`/cases/${c.id}`}>{c.number}</Link></td>
                <td className="td max-w-sm truncate">{c.title}</td><td className="td">{c.department}</td>
                <td className="td"><Badge k={c.urgency} /></td><td className="td"><Badge k={c.status} />{c.overdue && <span className="ms-1"><Badge k="Overdue" /></span>}{c.loop_closed && <span className="ms-1"><Badge k="green">Loop closed</Badge></span>}</td>
                <td className="td whitespace-nowrap">{c.owner}</td><td className="td whitespace-nowrap" style={c.overdue ? { color: "#dc2626", fontWeight: 600 } : {}}>{fmt(c.due_at)}</td>
              </tr>))}</tbody></table>}
        {data && <Pager page={f.page} size={f.size} total={data.total} onPage={(p) => setF({ ...f, page: p })} />}
      </div>
    </>
  );
}
export default function Page() { return <Suspense><Cases /></Suspense>; }

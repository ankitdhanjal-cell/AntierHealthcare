"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, qs } from "@/lib/api";
import { Badge, Empty, ErrorBox, PageHead, Pager, Skeleton, fmt, useFetch } from "@/components/ui";
import { useConfirm, useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

function Cases() {
  const sp = useSearchParams(); const me = useMe(); const toast = useToast(); const confirm = useConfirm();
  const [f, setF] = useState<any>({ page: 1, size: 15, sort: "created_at", order: "desc", overdue: sp.get("overdue") || "" });
  const [sel, setSel] = useState<string[]>([]);
  const [owner, setOwner] = useState("");
  const users = useFetch<any[]>(can(me, "users") ? "/users" : null);
  const { data, loading, error, reload } = useFetch<any>("/cases" + qs(f), [JSON.stringify(f)]);
  const set = (k: string, v: any) => setF({ ...f, [k]: v, page: 1 });
  const sort = (k: string) => setF({ ...f, sort: k, order: f.sort === k && f.order === "desc" ? "asc" : "desc" });
  const Th = ({ k, children }: any) => <th className="th cursor-pointer" onClick={() => sort(k)}>{children}{f.sort === k ? (f.order === "desc" ? " ↓" : " ↑") : ""}</th>;
  const bulkAssign = async () => { await api("/cases/bulk", { body: { ids: sel, owner_id: owner } }); toast(`${sel.length} cases assigned`); setSel([]); reload(); };
  const bulkClose = async () => {
    if (!(await confirm({ title: `Close ${sel.length} cases?`, body: "They will be marked Closed with a bulk-closure note.", label: "Close cases", danger: true }))) return;
    await api("/cases/bulk", { body: { ids: sel, close: true, resolution: "Closed in bulk by Quality team." } }); toast("Cases closed"); setSel([]); reload();
  };
  return (
    <>
      <PageHead title="Cases" sub="Complaints from patient feedback, tracked against SLA" />
      <div className="card p-3 mb-4 flex flex-wrap gap-2 items-center">
        <input className="input !w-56" placeholder="Search number or title…" onChange={(e) => set("q", e.target.value)} />
        <select className="input !w-40" value={f.status || ""} onChange={(e) => set("status", e.target.value)}><option value="">All statuses</option>{["New", "Assigned", "In investigation", "Resolved", "Closed"].map((s) => <option key={s}>{s}</option>)}</select>
        <select className="input !w-36" onChange={(e) => set("urgency", e.target.value)}><option value="">Any urgency</option><option>high</option><option>medium</option><option>low</option></select>
        <label className="text-sm flex items-center gap-1"><input type="checkbox" checked={!!f.overdue} onChange={(e) => set("overdue", e.target.checked ? "true" : "")} /> Overdue only</label>
        {sel.length > 0 && can(me, "cases", "approve") && <div className="ms-auto flex gap-2 items-center">
          <select className="input !w-48" value={owner} onChange={(e) => setOwner(e.target.value)}><option value="">Assign to…</option>{users.data?.filter((u) => u.active).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select>
          <button className="btn btn-ghost" disabled={!owner} onClick={bulkAssign}>Assign {sel.length}</button><button className="btn btn-danger" onClick={bulkClose}>Close {sel.length}</button></div>}
      </div>
      <div className="card overflow-x-auto">
        {loading ? <Skeleton /> : error ? <ErrorBox msg={error} retry={reload} /> : data.items.length === 0 ? <Empty title="No cases found" hint="Cases open automatically when a patient's feedback is not a happy one." /> :
          <table className="w-full"><thead><tr><th className="th w-8"></th><Th k="number">Case</Th><th className="th">Title</th><th className="th">Dept</th><Th k="urgency">Urgency</Th><Th k="status">Status</Th><th className="th">Owner</th><Th k="due_at">Due</Th></tr></thead>
            <tbody>{data.items.map((c: any) => (
              <tr key={c.id} className={c.overdue ? "bg-red-500/5" : ""}>
                <td className="td"><input type="checkbox" aria-label="Select case" checked={sel.includes(c.id)} onChange={(e) => setSel(e.target.checked ? [...sel, c.id] : sel.filter((x) => x !== c.id))} /></td>
                <td className="td"><Link className="underline font-medium" href={`/cases/${c.id}`}>{c.number}</Link></td>
                <td className="td max-w-sm truncate">{c.title}</td><td className="td">{c.department}</td>
                <td className="td"><Badge k={c.urgency} /></td><td className="td"><Badge k={c.status} />{c.overdue && <span className="ms-1"><Badge k="Overdue" /></span>}</td>
                <td className="td">{c.owner}</td><td className="td whitespace-nowrap" style={c.overdue ? { color: "#dc2626", fontWeight: 600 } : {}}>{fmt(c.due_at)}</td>
              </tr>))}</tbody></table>}
        {data && <Pager page={f.page} size={f.size} total={data.total} onPage={(p) => setF({ ...f, page: p })} />}
      </div>
    </>
  );
}
export default function Page() { return <Suspense><Cases /></Suspense>; }

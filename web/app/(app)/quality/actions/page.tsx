"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api } from "@/lib/api";
import { Badge, Empty, ErrorBox, PageHead, Skeleton, fmtDate, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

const SRC: Record<string, string> = { gap: "Accreditation gap", tracer: "Mock survey", audit: "Audit", capa: "Incident" };

function Register() {
  const sp = useSearchParams(); const me = useMe(); const toast = useToast();
  const [only, setOnly] = useState({ overdue: sp.get("overdue") === "true", mine: sp.get("mine") === "true" });
  const qa = useFetch<any[]>(can(me, "accreditation") || can(me, "audits") ? "/actions" : null);
  const capas = useFetch<any[]>(can(me, "incidents") ? "/incidents/capas" : null);
  if (qa.loading || capas.loading) return <><PageHead title="Actions register" /><Skeleton rows={5} /></>;
  const err = qa.error || capas.error;
  if (err) return <ErrorBox msg={err} retry={() => { qa.reload(); capas.reload(); }} />;
  const rows: any[] = [
    ...(capas.data || []).map((c) => ({ key: "c" + c.id, source: "capa", text: c.action, ref: c.incident_number, href: `/quality/incidents/${c.incident_id}`, owner: c.owner, owner_id: c.owner_id, due_at: c.due_at, status: c.status, overdue: c.overdue })),
    ...(qa.data || []).map((a) => ({ key: "a" + a.id, source: a.source_type, text: a.text, ref: "", href: a.element_id ? `/quality/accreditation/elements/${a.element_id}` : "/quality/audits", owner: a.owner, owner_id: a.owner_id, due_at: a.due_at, status: a.status, overdue: a.overdue, id: a.id })),
  ].filter((r) => (!only.overdue || r.overdue) && (!only.mine || r.owner_id === me.id)).sort((a, b) => +new Date(a.due_at) - +new Date(b.due_at));
  return (
    <>
      <PageHead title="Actions register" sub="Corrective and preventive actions from incidents, audits, mock surveys and accreditation gaps" />
      <div className="card p-3 mb-4 flex gap-4 text-sm">
        <label className="flex items-center gap-1.5"><input type="checkbox" checked={only.overdue} onChange={(e) => setOnly({ ...only, overdue: e.target.checked })} /> Overdue only</label>
        <label className="flex items-center gap-1.5"><input type="checkbox" checked={only.mine} onChange={(e) => setOnly({ ...only, mine: e.target.checked })} /> Assigned to me</label>
        <span className="ms-auto" style={{ color: "var(--muted)" }}>{rows.length} actions</span></div>
      <div className="card overflow-x-auto">
        {rows.length === 0 ? <Empty title="No actions match" hint="Clear a filter to see all actions." /> : (
          <table className="w-full"><thead><tr><th className="th">Action</th><th className="th">Source</th><th className="th">Owner</th><th className="th">Due</th><th className="th">Status</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.key} className={r.overdue ? "bg-red-500/5" : ""}>
                <td className="td min-w-[18rem]"><Link className="underline" href={r.href}>{r.text.slice(0, 160)}</Link></td><td className="td whitespace-nowrap">{SRC[r.source] || r.source}{r.ref ? ` · ${r.ref}` : ""}</td><td className="td">{r.owner}</td>
                <td className="td whitespace-nowrap" style={r.overdue ? { color: "#dc2626", fontWeight: 600 } : {}}>{fmtDate(r.due_at)}</td>
                <td className="td">{r.id && (r.owner_id === me.id || can(me, "accreditation", "create")) ? <select className="input !w-36" aria-label="Status" value={r.status} onChange={(e) => api(`/actions/${r.id}`, { method: "PUT", body: { status: e.target.value } }).then(() => { toast("Action updated"); qa.reload(); }).catch((x) => toast(x.message, "err"))}><option>Open</option><option>In progress</option><option>Completed</option></select> : <Badge k={r.status} />}</td></tr>))}</tbody></table>)}
      </div>
    </>
  );
}
export default function Page() { return <Suspense><Register /></Suspense>; }

"use client";
import { Fragment, useState } from "react";
import { qs } from "@/lib/api";
import { Empty, ErrorBox, PageHead, Pager, Skeleton, fmt, useFetch } from "@/components/ui";

export default function Audit() {
  const [f, setF] = useState<any>({ page: 1, size: 25 });
  const [open, setOpen] = useState<string | null>(null);
  const users = useFetch<any[]>("/users");
  const { data, loading, error, reload } = useFetch<any>("/audit" + qs(f), [JSON.stringify(f)]);
  const set = (k: string, v: any) => setF({ ...f, [k]: v, page: 1 });
  const exportUrl = "/api/audit/export" + qs({ module: f.module, user_id: f.user_id, q: f.q, record_id: f.record_id });
  return (
    <>
      <PageHead title="Audit trail" sub="Every create, edit, AI suggestion and status change">
        <button className="btn btn-ghost" onClick={async () => { const r = await fetch(exportUrl, { headers: { authorization: `Bearer ${localStorage.getItem("ahs_token")}` } }); const b = await r.blob(); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "audit-trail.csv"; a.click(); }}>Export CSV</button>
      </PageHead>
      <div className="card p-3 mb-4 grid grid-cols-2 md:grid-cols-4 gap-2">
        <input className="input" placeholder="Search…" onChange={(e) => set("q", e.target.value)} />
        <select className="input" onChange={(e) => set("module", e.target.value)}><option value="">All modules</option>{["auth", "feedback", "cases", "integrations", "settings", "users"].map((m) => <option key={m}>{m}</option>)}</select>
        <select className="input" onChange={(e) => set("user_id", e.target.value)}><option value="">All users</option>{users.data?.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select>
        <input className="input" placeholder="Record id" onChange={(e) => set("record_id", e.target.value)} />
      </div>
      <div className="card overflow-x-auto">
        {loading ? <Skeleton /> : error ? <ErrorBox msg={error} retry={reload} /> : !data.items.length ? <Empty title="No audit entries" hint="Adjust the filters." /> :
          <table className="w-full"><thead><tr><th className="th">When</th><th className="th">User</th><th className="th">Module</th><th className="th">Action</th><th className="th">Summary</th><th className="th"></th></tr></thead>
            <tbody>{data.items.map((a: any) => <Fragment key={a.id}>
              <tr><td className="td whitespace-nowrap">{fmt(a.at)}</td><td className="td">{a.user}</td><td className="td">{a.module}</td><td className="td">{a.action}</td><td className="td">{a.summary}</td>
                <td className="td">{(a.before || a.after) && <button className="text-xs underline" onClick={() => setOpen(open === a.id ? null : a.id)}>{open === a.id ? "Hide" : "Before / after"}</button>}</td></tr>
              {open === a.id && <tr><td colSpan={6} className="td"><div className="grid md:grid-cols-2 gap-2 text-xs"><pre className="p-2 rounded overflow-auto" style={{ background: "var(--line)" }}>Before{"\n"}{JSON.stringify(a.before, null, 2)}</pre><pre className="p-2 rounded overflow-auto" style={{ background: "var(--line)" }}>After{"\n"}{JSON.stringify(a.after, null, 2)}</pre></div></td></tr>}</Fragment>)}</tbody></table>}
        {data && <Pager page={f.page} size={f.size} total={data.total} onPage={(p) => setF({ ...f, page: p })} />}
      </div>
    </>
  );
}

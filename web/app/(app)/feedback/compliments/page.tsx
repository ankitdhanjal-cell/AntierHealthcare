"use client";
import Link from "next/link";
import { useState } from "react";
import { api, fetchAllPages, qs } from "@/lib/api";
import { Badge, Empty, ErrorBox, PageHead, Pager, Skeleton, fmtDate, useFetch } from "@/components/ui";
import { ExportBar } from "@/components/ExportBar";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

export default function Compliments() {
  const me = useMe(); const toast = useToast();
  const [f, setF] = useState<any>({ page: 1, size: 12, staff: "", shared: "" });
  const { data, loading, error, reload } = useFetch<any>("/feedback/compliments" + qs(f), [JSON.stringify(f)]);
  const share = async (id: string) => { try { const r = await api(`/feedback/${id}/share-compliment`, { body: {} }); toast(`Shared with ${r.shared_with}`); reload(); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <>
      <PageHead title="Compliments" sub="Positive comments that name a member of staff. Share them with the department head.">
        <ExportBar filename="compliments" fetchAll={() => fetchAllPages("/feedback/compliments", f).then((r) => r)} columns={[["Received", (r) => fmtDate(r.created_at)], ["Staff named", (r) => r.staff_mentions.join("; ")], ["Department", (r) => r.department],
          ["Comment", (r) => r.text], ["English translation", (r) => r.translation], ["Shared with department", (r) => (r.shared_at ? fmtDate(r.shared_at) : "")]]} /></PageHead>
      {data?.top_staff?.length > 0 && <div className="card p-4 mb-4"><div className="text-xs mb-2" style={{ color: "var(--muted)" }}>Most mentioned staff</div>
        <div className="flex flex-wrap gap-2">{data.top_staff.map((s: any) => <button key={s.name} className="px-2.5 py-1 rounded-full text-sm border" style={f.staff === s.name ? { background: "var(--brand)", color: "#fff", borderColor: "var(--brand)" } : { borderColor: "var(--line)" }}
          onClick={() => setF({ ...f, staff: f.staff === s.name ? "" : s.name, page: 1 })}>{s.name} <span className="opacity-70">{s.count}</span></button>)}</div></div>}
      <div className="card p-3 mb-4 flex gap-3 items-center text-sm"><select className="input !w-48" aria-label="Shared" value={f.shared} onChange={(e) => setF({ ...f, shared: e.target.value, page: 1 })}><option value="">All compliments</option><option value="false">Not shared yet</option><option value="true">Shared</option></select>
        {f.staff && <button className="underline" onClick={() => setF({ ...f, staff: "", page: 1 })}>Clear “{f.staff}”</button>}</div>
      {loading && !data ? <Skeleton rows={4} /> : error || !data ? <ErrorBox msg={error} retry={reload} /> : data.items.length === 0 ? <Empty title="No compliments match" hint="Positive comments that mention a staff member by name appear here." /> : (
        <div className="space-y-3">{data.items.map((c: any) => (
          <div key={c.id} className="card p-4 text-sm">
            <div className="flex flex-wrap justify-between gap-2"><div className="flex flex-wrap gap-1.5">{c.staff_mentions.map((s: string) => <Badge key={s} k="green">{s}</Badge>)}<span className="text-xs self-center" style={{ color: "var(--muted)" }}>{c.department} · {fmtDate(c.created_at)} · {"★".repeat(c.rating)}</span></div>
              <div className="text-xs flex gap-3 items-center"><Link className="underline" href={`/feedback/${c.id}`}>Open</Link>
                {c.shared_at ? <span style={{ color: "var(--muted)" }}>Shared {fmtDate(c.shared_at)}</span> : can(me, "feedback", "create") && <button className="btn btn-ghost" onClick={() => share(c.id)}>Share with department</button>}</div></div>
            <p className="mt-2" dir={c.language === "ar" ? "rtl" : "ltr"}>{c.text}</p>
            {c.language === "ar" && c.translation && <p className="mt-1" style={{ color: "var(--muted)" }}>English: {c.translation}</p>}
          </div>))}
          <div className="card"><Pager page={f.page} size={f.size} total={data.total} onPage={(p) => setF({ ...f, page: p })} /></div></div>)}
    </>
  );
}

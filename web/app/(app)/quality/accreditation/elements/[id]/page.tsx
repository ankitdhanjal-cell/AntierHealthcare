"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api, getToken } from "@/lib/api";
import { Badge, ErrorBox, PageHead, Skeleton, dayEndIso, fmt, fmtDate, inDays, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

export default function Element() {
  const { id } = useParams<{ id: string }>(); const me = useMe(); const toast = useToast();
  const { data: e, loading, error, reload } = useFetch<any>(`/accreditation/elements/${id}`);
  const users = useFetch<any[]>(can(me, "users") ? "/users" : null);
  const capas = useFetch<any[]>(can(me, "incidents") ? "/incidents/capas?status=Completed" : null);
  const [note, setNote] = useState<string | null>(null); const [file, setFile] = useState<File | null>(null); const [title, setTitle] = useState(""); const [met, setMet] = useState(false);
  const [act, setAct] = useState({ text: "", due: inDays(30) }); const [pick, setPick] = useState("");
  if (loading && !e) return <Skeleton rows={5} />;
  if (error || !e) return <ErrorBox msg={error} retry={reload} />;
  const canEdit = can(me, "accreditation", "create");
  const run = (fn: () => Promise<any>, ok: string) => fn().then(() => { toast(ok); reload(); }).catch((x: any) => toast(x.message, "err"));
  const upload = async () => {
    const fd = new FormData(); fd.append("file", file!); fd.append("title", title); fd.append("mark_met", String(met));
    const r = await fetch(`/api/accreditation/elements/${id}/evidence`, { method: "POST", headers: { authorization: `Bearer ${getToken()}` }, body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || "Upload failed");
    setFile(null); setTitle("");
  };
  const download = async (v: any) => {
    const r = await fetch(`/api/accreditation/evidence/${v.id}/download`, { headers: { authorization: `Bearer ${getToken()}` } });
    if (!r.ok) return toast("File not found", "err");
    const url = URL.createObjectURL(await r.blob()); const a = document.createElement("a"); a.href = url; a.download = v.filename; a.click(); URL.revokeObjectURL(url);
  };
  return (
    <>
      <PageHead title={`${e.code} · ${e.standard_title}`} sub={e.chapter}><Badge k={e.status} /></PageHead>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <div className="card p-4 text-sm space-y-2"><div className="label">Measurable element</div><p>{e.text}</p>
            {e.review_overdue && <p className="text-xs text-amber-700">Not reviewed in the last 180 days.</p>}</div>
          <div className="card p-4 text-sm">
            <div className="font-medium mb-2">Evidence ({e.evidence.length})</div>
            {e.evidence.length === 0 ? <p style={{ color: "var(--muted)" }}>No evidence attached. Upload a document or attach a completed action or audit.</p> :
              <ul className="divide-y" style={{ borderColor: "var(--line)" }}>{e.evidence.map((v: any) => (
                <li key={v.id} className="py-2 flex flex-wrap items-center gap-2 justify-between"><div className="min-w-0"><Badge k={v.kind === "file" ? "neutral" : "Triaged"}>{v.kind === "file" ? "Document" : v.kind === "capa" ? "Corrective action" : "Audit"}</Badge> <span className="ms-1">{v.title}</span>
                  <span className="block text-xs" style={{ color: "var(--muted)" }}>Added by {v.added_by} · {fmt(v.created_at)}</span></div>
                  <div className="flex gap-3 text-xs">{v.kind === "file" && <button className="underline" onClick={() => download(v)}>Download</button>}
                    {v.kind === "capa" && v.source_id && <Link className="underline" href="/quality/incidents">Open incidents</Link>}
                    {can(me, "accreditation", "approve") && <button className="underline text-red-600" onClick={() => run(() => api(`/accreditation/evidence/${v.id}`, { method: "DELETE" }), "Evidence removed")}>Remove</button>}</div></li>))}</ul>}
            {canEdit && <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 pt-3" style={{ borderTop: "1px solid var(--line)" }}>
              <div className="space-y-2"><div className="label">Upload a document</div>
                <input type="file" aria-label="Evidence file" accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx" onChange={(ev) => setFile(ev.target.files?.[0] || null)} />
                <input className="input" placeholder="Title (optional)" aria-label="Evidence title" value={title} onChange={(ev) => setTitle(ev.target.value)} />
                <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={met} onChange={(ev) => setMet(ev.target.checked)} /> Mark the element as Met</label>
                <button className="btn" disabled={!file} onClick={() => run(upload, "Evidence uploaded")}>Upload</button></div>
              <div className="space-y-2"><div className="label">Attach a completed corrective action</div>
                <select className="input" aria-label="Completed action" value={pick} onChange={(ev) => setPick(ev.target.value)}><option value="">Choose…</option>{(capas.data || []).map((c) => <option key={c.id} value={c.id}>{c.incident_number} · {c.action.slice(0, 60)}</option>)}</select>
                <button className="btn btn-ghost" disabled={!pick} onClick={() => run(() => api(`/accreditation/elements/${id}/attach`, { body: { source_type: "capa", source_id: pick, mark_met: true } }), "Attached as evidence").then(() => setPick(""))}>Attach and mark Met</button>
                <p className="text-xs" style={{ color: "var(--muted)" }}>Completed audits can be attached from the audit result page.</p></div></div>}
          </div>
          <div className="card p-4 text-sm">
            <div className="font-medium mb-2">Actions</div>
            {e.actions.length === 0 ? <p style={{ color: "var(--muted)" }}>No actions for this element.</p> : <ul className="space-y-2">{e.actions.map((a: any) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2"><span className="min-w-0">{a.text}<span className="block text-xs" style={{ color: a.overdue ? "#dc2626" : "var(--muted)" }}>{a.owner} · due {fmtDate(a.due_at)}{a.overdue ? " (overdue)" : ""}</span></span>
                <select className="input !w-36" aria-label="Action status" value={a.status} onChange={(ev) => run(() => api(`/actions/${a.id}`, { method: "PUT", body: { status: ev.target.value } }), "Action updated")}><option>Open</option><option>In progress</option><option>Completed</option></select></li>))}</ul>}
            {canEdit && <div className="mt-3 grid grid-cols-1 md:grid-cols-4 gap-2 items-end"><div className="md:col-span-2"><label className="label" htmlFor="at">New action</label><input id="at" className="input" value={act.text} onChange={(ev) => setAct({ ...act, text: ev.target.value })} placeholder="What will close the gap?" /></div>
              <div><label className="label" htmlFor="ad">Due</label><input id="ad" type="date" className="input" value={act.due} onChange={(ev) => setAct({ ...act, due: ev.target.value })} /></div>
              <button className="btn" disabled={act.text.trim().length < 5} onClick={() => run(async () => { await api("/actions", { body: { text: act.text, element_id: id, owner_id: e.owner_id, due_at: dayEndIso(act.due) } }); setAct({ text: "", due: inDays(30) }); }, "Action added")}>Add action</button></div>}
          </div>
        </div>
        <div className="space-y-4">
          {canEdit && <div className="card p-4 space-y-2 text-sm"><div className="font-medium">Review</div>
            <label className="label" htmlFor="st">Status</label><select id="st" className="input" value={e.status} onChange={(ev) => run(() => api(`/accreditation/elements/${id}`, { method: "PUT", body: { status: ev.target.value } }), "Status saved")}>{["Met", "Partially met", "Not met", "Not applicable"].map((o) => <option key={o}>{o}</option>)}</select>
            {users.data && <><label className="label" htmlFor="ow">Owner</label><select id="ow" className="input" value={e.owner_id || ""} onChange={(ev) => run(() => api(`/accreditation/elements/${id}`, { method: "PUT", body: { owner_id: ev.target.value } }), "Owner saved")}><option value="">Unassigned</option>{users.data.filter((u) => u.active).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></>}
            <label className="label" htmlFor="nt">Note</label><textarea id="nt" className="input" rows={3} value={note ?? e.note} onChange={(ev) => setNote(ev.target.value)} />
            <button className="btn w-full justify-center" disabled={note === null} onClick={() => run(() => api(`/accreditation/elements/${id}`, { method: "PUT", body: { note } }), "Note saved").then(() => setNote(null))}>Save note</button>
            <p className="text-xs" style={{ color: "var(--muted)" }}>Owner: {e.owner} · last reviewed {fmtDate(e.last_reviewed_at)}</p></div>}
        </div>
      </div>
    </>
  );
}

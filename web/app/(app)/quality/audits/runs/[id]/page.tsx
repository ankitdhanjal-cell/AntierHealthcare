"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api, getToken } from "@/lib/api";
import { Badge, ErrorBox, PageHead, PctBar, Skeleton, fmtDate, fmtMonth, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";
import { AttachEvidence } from "@/components/AttachEvidence";

export default function AuditRunPage() {
  const { id } = useParams<{ id: string }>(); const toast = useToast(); const me = useMe();
  const { data: r, loading, error, reload } = useFetch<any>(`/audits/runs/${id}`);
  const [local, setLocal] = useState<Record<string, { result: string; comment: string }>>({});
  const [summary, setSummary] = useState(""); const [busy, setBusy] = useState(false);
  if (loading && !r) return <Skeleton rows={6} />;
  if (error || !r) return <ErrorBox msg={error} retry={reload} />;
  const done = r.status === "Completed"; const edit = r.can_work && !done;
  const val = (it: any) => local[it.key] ?? { result: it.result, comment: it.comment };
  const answered = r.items.filter((it: any) => val(it).result).length;
  const save = async (key: string, patch: any) => {
    const cur = { ...val(r.items.find((i: any) => i.key === key)), ...patch };
    setLocal({ ...local, [key]: cur });
    if (!cur.result) return;
    try { await api(`/audits/runs/${id}/answers`, { method: "PUT", body: { answers: [{ key, result: cur.result, comment: cur.comment || "" }] } }); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const photo = async (key: string, file?: File | null) => {
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    const res = await fetch(`/api/audits/runs/${id}/photo/${key}`, { method: "POST", headers: { authorization: `Bearer ${getToken()}` }, body: fd });
    if (!res.ok) return toast((await res.json()).detail || "Upload failed", "err");
    toast("Photo added"); reload();
  };
  const complete = async () => {
    setBusy(true);
    try { const x = await api(`/audits/runs/${id}/complete`, { body: { comment: summary } }); toast(`Audit completed: ${x.score}% compliance`); reload(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const Btn = ({ it, value, label, tone }: any) => <button type="button" aria-pressed={val(it).result === value} disabled={!edit} onClick={() => save(it.key, { result: value })}
    className="flex-1 min-h-[3rem] rounded-lg text-sm font-semibold border" style={val(it).result === value ? { background: tone, color: "#fff", borderColor: tone } : { borderColor: "var(--line)" }}>{label}</button>;
  return (
    <>
      <PageHead title={r.template} sub={`${r.unit || r.department} · ${fmtMonth(r.period)} · auditor ${r.auditor}`}>
        {done ? <Badge k="Completed" /> : r.overdue ? <Badge k="Overdue" /> : <Badge k="Scheduled" />}
      </PageHead>
      {done && <div className="card p-4 mb-4 flex flex-wrap items-center gap-4">
        <div><div className="text-xs" style={{ color: "var(--muted)" }}>Compliance</div><div className="text-3xl font-semibold" style={{ color: r.on_target ? "#0f9d6b" : "#dc2626" }}>{r.score}%</div></div>
        <div className="flex-1 min-w-[10rem]"><PctBar pct={r.score} target={r.target} color={r.on_target ? "#0f9d6b" : "#dc4a3d"} /><div className="text-xs mt-1" style={{ color: "var(--muted)" }}>Target {r.target}% · {r.yes} yes, {r.no} no · completed {fmtDate(r.completed_at)}</div></div>
        {can(me, "accreditation", "create") && <AttachEvidence sourceType="audit_run" sourceId={r.id} />}
        {r.comment && <p className="w-full text-sm">{r.comment}</p>}</div>}
      {edit && <div className="mb-3"><div className="flex justify-between text-xs mb-1" style={{ color: "var(--muted)" }}><span>{r.description}</span><span>{answered} of {r.items.length}</span></div><PctBar pct={(100 * answered) / r.items.length} /></div>}
      <div className="space-y-3 max-w-3xl">{r.items.map((it: any, n: number) => (
        <div key={it.key} className="card p-4">
          <div className="text-sm mb-3"><span className="text-xs me-2" style={{ color: "var(--muted)" }}>{n + 1}</span>{it.text}</div>
          <div className="flex gap-2" role="group" aria-label={`Answer for question ${n + 1}`}><Btn it={it} value="yes" label="Yes" tone="#0f9d6b" /><Btn it={it} value="no" label="No" tone="#dc4a3d" /><Btn it={it} value="na" label="N/A" tone="#64748b" /></div>
          {(edit || val(it).comment) && <input className="input mt-2" aria-label={`Comment on question ${n + 1}`} placeholder={val(it).result === "no" ? "What was found? (a comment is expected for a No)" : "Comment (optional)"} disabled={!edit} value={val(it).comment} onChange={(e) => setLocal({ ...local, [it.key]: { ...val(it), comment: e.target.value } })} onBlur={() => save(it.key, {})} />}
          {edit && <label className="block mt-2 text-xs underline" style={val(it).result ? { cursor: "pointer" } : { opacity: 0.5 }}>{it.has_photo ? "Replace photo" : "Add a photo"}{!val(it).result && " (answer first)"}<input type="file" disabled={!val(it).result} accept="image/*" capture="environment" className="hidden" onChange={(e) => photo(it.key, e.target.files?.[0])} /></label>}
          {it.has_photo && <a className="block mt-1 text-xs underline" href="#" onClick={async (e) => { e.preventDefault(); const x = await fetch(`/api/audits/runs/${id}/photo/${it.key}`, { headers: { authorization: `Bearer ${getToken()}` } }); const u = URL.createObjectURL(await x.blob()); window.open(u, "_blank"); }}>View photo</a>}
          {done && it.result === "no" && (it.action ? <p className="mt-2 text-xs">Action: {it.action.text} <span style={{ color: "var(--muted)" }}>· {it.action.owner}, due {fmtDate(it.action.due_at)}</span></p> :
            can(me, "audits", "create") && <button className="btn btn-ghost mt-2" onClick={async () => { try { await api(`/audits/runs/${id}/answers/${it.key}/action`, { body: {} }); toast("Corrective action raised, due in 14 days"); reload(); } catch (e: any) { toast(e.message, "err"); } }}>Raise corrective action</button>)}
        </div>))}</div>
      {edit && <div className="card p-4 mt-4 max-w-3xl space-y-2"><label className="label" htmlFor="sum">Summary comment (optional)</label><textarea id="sum" className="input" rows={2} value={summary} onChange={(e) => setSummary(e.target.value)} />
        <button className="btn" disabled={busy || answered < r.items.length} onClick={complete}>{answered < r.items.length ? `Answer all ${r.items.length} questions to complete` : "Complete audit"}</button></div>}
      <p className="mt-4"><Link className="text-sm underline" href="/quality/audits">Back to audits</Link></p>
    </>
  );
}

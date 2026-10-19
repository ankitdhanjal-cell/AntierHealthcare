"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Badge, ErrorBox, PageHead, PctBar, Skeleton, fmtDate, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

const OPTIONS = ["Met", "Partially met", "Not met", "Not applicable"];

export default function Tracer() {
  const { id } = useParams<{ id: string }>(); const me = useMe(); const toast = useToast();
  const { data: t, loading, error, reload } = useFetch<any>(`/accreditation/tracers/${id}`);
  const [notes, setNotes] = useState<Record<string, string>>({});
  if (loading && !t) return <Skeleton rows={6} />;
  if (error || !t) return <ErrorBox msg={error} retry={reload} />;
  const open = !t.completed_at && can(me, "accreditation", "create");
  const run = (fn: () => Promise<any>, ok: string) => fn().then(() => { toast(ok); reload(); }).catch((x: any) => toast(x.message, "err"));
  const record = (eid: string, result: string) => run(() => api(`/accreditation/tracers/${id}/results/${eid}`, { method: "PUT", body: { result, note: notes[eid] ?? "" } }), `Recorded: ${result}`);
  const pct = t.progress.total ? Math.round((100 * t.progress.done) / t.progress.total) : 0;
  return (
    <>
      <PageHead title={`Mock survey · ${t.chapter.code} ${t.chapter.name}`} sub={`${t.progress.done} of ${t.progress.total} elements walked${t.completed_at ? " · completed" : ""}`}>
        {open && <button className="btn" onClick={() => run(() => api(`/accreditation/tracers/${id}/complete`, { body: {} }), "Mock survey completed")}>Finish survey</button>}
        <Link className="btn btn-ghost" href="/quality/accreditation">Back to readiness</Link>
      </PageHead>
      <div className="max-w-md mb-4"><PctBar pct={pct} /></div>
      <p className="text-sm mb-4 max-w-2xl" style={{ color: "var(--muted)" }}>Walk each element as a surveyor would. Your finding updates the element status and the readiness figure. For any gap, create an action in one click.</p>
      <div className="space-y-3">{t.elements.map((e: any) => (
        <div key={e.id} className="card p-4 text-sm">
          <div className="flex flex-wrap justify-between gap-2"><div className="min-w-0 max-w-3xl"><b>{e.code}</b> {e.text}<span className="block text-xs" style={{ color: "var(--muted)" }}>Owner {e.owner} · {e.evidence_count ? "evidence on file" : "no evidence on file"}</span></div>
            {e.result && <Badge k={e.result} />}</div>
          {open ? <div className="mt-3 space-y-2">
            <div className="flex flex-wrap gap-2">{OPTIONS.map((o) => <button key={o} className={`btn ${e.result === o ? "" : "btn-ghost"}`} onClick={() => record(e.id, o)}>{o}</button>)}</div>
            {(e.result === "Partially met" || e.result === "Not met" || notes[e.id] !== undefined) && <input className="input" aria-label={`Finding for ${e.code}`} placeholder="Finding (what the surveyor saw)" value={notes[e.id] ?? e.finding ?? ""} onChange={(ev) => setNotes({ ...notes, [e.id]: ev.target.value })} onBlur={() => e.result && notes[e.id] !== undefined && record(e.id, e.result)} />}
          </div> : e.finding && <p className="mt-2 text-xs">Finding: {e.finding}</p>}
          {(e.result === "Partially met" || e.result === "Not met") && (e.action ? <p className="mt-2 text-xs">Action: {e.action.text} <span style={{ color: "var(--muted)" }}>· {e.action.owner}, due {fmtDate(e.action.due_at)}</span></p> :
            open && <button className="btn btn-ghost mt-2" onClick={() => run(() => api(`/accreditation/tracers/${id}/results/${e.id}/action`, { body: {} }), "Action created, due in 30 days")}>Create action</button>)}
        </div>))}</div>
    </>
  );
}

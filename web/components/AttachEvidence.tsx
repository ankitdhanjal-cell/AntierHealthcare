"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "./ui";
import { useToast } from "./Providers";

/** One-click evidence link: pick an accreditation element and attach a completed action or audit to it. */
export function AttachEvidence({ sourceType, sourceId, onDone }: { sourceType: "capa" | "audit_run"; sourceId: string; onDone?: () => void }) {
  const [open, setOpen] = useState(false); const [el, setEl] = useState(""); const [met, setMet] = useState(true); const [err, setErr] = useState("");
  const toast = useToast();
  const list = useFetch<any[]>(open ? "/accreditation/elements" : null);
  const go = async () => {
    setErr("");
    try { const r = await api(`/accreditation/elements/${el}/attach`, { body: { source_type: sourceType, source_id: sourceId, mark_met: met } }); toast(`Attached as evidence. Readiness is now ${r.readiness.pct}%`); setOpen(false); onDone?.(); }
    catch (e: any) { setErr(e.message); }
  };
  if (!open) return <button className="text-xs underline" onClick={() => setOpen(true)}>Attach as evidence</button>;
  return (
    <div className="mt-1 p-2 rounded-md space-y-1.5 text-xs" style={{ background: "var(--line)" }}>
      <select className="input" aria-label="Accreditation element" value={el} onChange={(e) => setEl(e.target.value)}>
        <option value="">Choose a standard element…</option>
        {(list.data || []).map((e) => <option key={e.id} value={e.id}>{e.code} · {e.text.slice(0, 70)} ({e.status})</option>)}</select>
      <label className="flex items-center gap-1.5"><input type="checkbox" checked={met} onChange={(e) => setMet(e.target.checked)} /> Mark the element as Met</label>
      {err && <p className="text-red-600">{err}</p>}
      <div className="flex gap-2"><button className="btn" disabled={!el} onClick={go}>Attach</button><button className="btn btn-ghost" onClick={() => setOpen(false)}>Cancel</button></div>
    </div>
  );
}

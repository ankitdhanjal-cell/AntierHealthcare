"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { PageHead, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";

const localNow = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };

export default function ReportIncident() {
  const toast = useToast();
  const meta = useFetch<any>("/incidents/meta");
  const [f, setF] = useState<any>({ description: "", occurred: localNow(), category: "", harm: "", department_id: "", location: "", immediate_action: "", anonymous: false });
  const [sug, setSug] = useState<any>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [done, setDone] = useState<any>(null);
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const suggest = async () => {
    setErr("");
    try { const s = await api("/incidents/ai-suggest", { body: { text: f.description, department_id: f.department_id || null } }); setSug(s); setF({ ...f, category: f.category || s.category, harm: f.harm || s.harm }); }
    catch (e: any) { setErr(e.message); }
  };
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api("/incidents", { body: { description: f.description, occurred_at: new Date(f.occurred).toISOString(), category: f.category || null, harm: f.harm || null,
        department_id: f.department_id || null, location: f.location, immediate_action: f.immediate_action, anonymous: f.anonymous } });
      setDone(r); toast(`Incident ${r.number} reported`);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  if (done) return (
    <div className="card p-8 max-w-xl mx-auto text-center">
      <h1 className="text-xl font-semibold">Thank you for reporting</h1>
      <p className="text-sm mt-2" style={{ color: "var(--muted)" }}>Your report is {done.number}.{done.sentinel ? " It has been flagged as a serious event and the Quality Manager has been notified." : " The Quality team will review it."}{f.anonymous ? " It was sent anonymously." : ""}</p>
      <div className="flex gap-2 justify-center mt-5"><button className="btn btn-ghost" onClick={() => { setDone(null); setSug(null); setF({ ...f, description: "", immediate_action: "", location: "", category: "", harm: "", occurred: localNow() }); }}>Report another</button>
        {!f.anonymous && <Link className="btn" href={`/quality/incidents/${done.id}`}>View report</Link>}<Link className="btn btn-ghost" href="/quality/incidents">Back to incidents</Link></div>
    </div>
  );
  const ok = f.description.trim().length >= 10;
  return (
    <>
      <PageHead title="Report an incident" sub="Takes about a minute. Describe what happened, not who was at fault." />
      <div className="card p-5 max-w-3xl space-y-4">
        <div><label className="label" htmlFor="desc">What happened?</label>
          <textarea id="desc" className="input" rows={5} value={f.description} onChange={(e) => set("description", e.target.value)} placeholder="For example: patient found on the floor beside the bed at 03:00, no visible injury…" />
          <div className="mt-2 flex items-center gap-3"><button className="btn btn-ghost" disabled={!ok} onClick={suggest}>Suggest category and harm level</button><span className="text-xs" style={{ color: "var(--muted)" }}>Optional. You can change the suggestion.</span></div>
          {sug && <div className="mt-2 p-3 rounded-lg text-sm" style={{ background: "var(--line)" }}>
            <b>Suggested:</b> {meta.data?.categories.find((c: any) => c.key === sug.category)?.label} · {meta.data?.harms.find((c: any) => c.key === sug.harm)?.label}{sug.status === "needs_review" && " (needs review)"}
            {sug.similar?.label && <div className="mt-1">{sug.similar.label}.</div>}</div>}</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div><label className="label" htmlFor="when">When did it happen?</label><input id="when" type="datetime-local" className="input" value={f.occurred} max={localNow()} onChange={(e) => set("occurred", e.target.value)} /></div>
          <div><label className="label" htmlFor="dept">Department</label><select id="dept" className="input" value={f.department_id} onChange={(e) => set("department_id", e.target.value)}><option value="">Choose…</option>{meta.data?.departments.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
          <div><label className="label" htmlFor="loc">Where exactly? (ward, room, bed)</label><input id="loc" className="input" value={f.location} onChange={(e) => set("location", e.target.value)} placeholder="Ward 2, bed 14" /></div>
          <div><label className="label" htmlFor="cat">Category</label><select id="cat" className="input" value={f.category} onChange={(e) => set("category", e.target.value)}><option value="">Let the system suggest</option>{meta.data?.categories.map((c: any) => <option key={c.key} value={c.key}>{c.label}</option>)}</select></div>
          <div><label className="label" htmlFor="harm">Harm level</label><select id="harm" className="input" value={f.harm} onChange={(e) => set("harm", e.target.value)}><option value="">Let the system suggest</option>{meta.data?.harms.map((c: any) => <option key={c.key} value={c.key}>{c.label}</option>)}</select></div>
        </div>
        <div><label className="label" htmlFor="act">Immediate action taken</label><textarea id="act" className="input" rows={2} value={f.immediate_action} onChange={(e) => set("immediate_action", e.target.value)} /></div>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={f.anonymous} onChange={(e) => set("anonymous", e.target.checked)} />
          <span>Report anonymously<span className="block text-xs" style={{ color: "var(--muted)" }}>Your name is not stored with the report. Reports are used to improve safety, not to blame individuals.</span></span></label>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <div className="flex gap-2"><button className="btn" disabled={!ok || busy} onClick={submit}>{busy ? "Sending…" : "Submit report"}</button><Link href="/quality/incidents" className="btn btn-ghost">Cancel</Link></div>
      </div>
    </>
  );
}

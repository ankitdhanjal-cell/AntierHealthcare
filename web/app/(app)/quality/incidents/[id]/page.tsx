"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { AiTag, Badge, ErrorBox, PageHead, Skeleton, fmt, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { AttachEvidence } from "@/components/AttachEvidence";
import { can, useMe } from "@/components/Shell";

const toIso = (v: string) => new Date(v).toISOString();
const dayEnd = (v: string) => new Date(v + "T23:59").toISOString();
const dateInput = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString("en-CA") : "");
const localInput = (iso?: string | null) => { const d = iso ? new Date(iso) : new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };
const KIND: Record<string, string> = { fact: "Fact", reported: "Reported", triaged: "Triage", escalated: "Escalation", capa: "Action", closed: "Closed", status: "Status", note: "Update", linked: "Linked" };

export default function IncidentView() {
  const { id } = useParams<{ id: string }>();
  const { data: i, loading, error, reload } = useFetch<any>(`/incidents/${id}`);
  const meta = useFetch<any>("/incidents/meta");
  if (loading && !i) return <Skeleton rows={6} />;
  if (error || !i) return <ErrorBox msg={error} retry={reload} />;
  return <Workspace i={i} meta={meta.data} reload={reload} />;
}

function Workspace({ i, meta, reload }: { i: any; meta: any; reload: () => void }) {
  const toast = useToast(); const me = useMe();
  const [err, setErr] = useState("");
  const closed = i.status === "Closed";
  const editable = i.can_work && !closed;
  const act = async (fn: () => Promise<any>, ok: string) => { setErr(""); try { await fn(); toast(ok); reload(); } catch (e: any) { setErr(e.message); toast(e.message, "err"); } };

  // triage
  const [tri, setTri] = useState<any>({ category: i.category, harm: i.harm, investigator_id: i.investigator_id || "", due: dateInput(i.due_at) });
  // investigation
  const [factors, setFactors] = useState<Record<string, string>>(Object.fromEntries(Object.entries(i.contributing_factors).map(([k, v]: any) => [k, v.join("\n")])));
  const [whys, setWhys] = useState<string[]>([0, 1, 2, 3, 4].map((n) => i.why_chain[n] || ""));
  const [root, setRoot] = useState(i.root_cause || "");
  const [fact, setFact] = useState({ at: localInput(), text: "" });
  // CAPA
  const [capa, setCapa] = useState<any>({ kind: "corrective", action: "", owner_id: "", due: "", check: "" });

  const saveInvestigation = () => act(() => api(`/incidents/${i.id}/investigation`, { method: "PUT", body: {
    contributing_factors: Object.fromEntries(Object.entries(factors).map(([k, v]) => [k, v.split("\n")])), why_chain: whys, root_cause: root } }), "Investigation saved");
  const addCapa = () => act(async () => {
    await api(`/incidents/${i.id}/capas`, { body: { kind: capa.kind, action: capa.action, owner_id: capa.owner_id || null, due_at: dayEnd(capa.due), check_due_at: capa.check ? dayEnd(capa.check) : null } });
    setCapa({ kind: "corrective", action: "", owner_id: "", due: "", check: "" });
  }, "Action added");
  const patchCapa = (cid: string, body: any, ok: string) => act(() => api(`/incidents/capas/${cid}`, { method: "PUT", body }), ok);

  return (
    <>
      <PageHead title={`${i.number} · ${i.title}`} sub={`${i.department}${i.location ? " · " + i.location : ""} · occurred ${fmt(i.occurred_at)}`}>
        {i.sentinel && <Badge k="Sentinel">Serious event</Badge>}<Badge k={i.harm}>{i.harm_label}</Badge><Badge k={i.status} />{i.overdue && <Badge k="Overdue" />}
      </PageHead>
      {i.sentinel && <div className="mb-4 p-3 rounded-lg text-sm bg-red-500/10" style={{ border: "1px solid #dc262655" }}>
        <b>Serious event.</b> Investigation due {fmt(i.due_at)}. {i.escalated_at ? `Escalated to management on ${fmt(i.escalated_at)}.` : "Not yet escalated to management."}</div>}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <div className="card p-4 space-y-3 text-sm">
            <div className="font-medium">What happened <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· reported by {i.reporter} on {fmt(i.created_at)}</span>{i.ai?.provider && <AiTag />}</div>
            <p className="whitespace-pre-line">{i.description}</p>
            {i.immediate_action && <div><span className="label">Immediate action</span>{i.immediate_action}</div>}
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
              <span>Category: {i.category_label}</span>{i.patient && <span>Patient: {i.patient}</span>}
              {i.case && <span>Linked complaint: <Link className="underline" href={`/cases/${i.case.id}`}>{i.case.number}</Link></span>}</div>
          </div>
          {i.similar.label && <div className="card p-4 text-sm"><div className="font-medium mb-1">Similar incidents</div><p>{i.similar.label}.</p>
            {i.similar.items?.length > 0 && <ul className="mt-2 space-y-1">{i.similar.items.map((s: any) => <li key={s.id}><Link className="underline" href={`/quality/incidents/${s.id}`}>{s.number}</Link> · {s.title} <span className="text-xs" style={{ color: "var(--muted)" }}>({fmt(s.occurred_at)}, {s.harm_label})</span></li>)}</ul>}</div>}

          <div className="card p-4 space-y-4 text-sm">
            <div className="font-medium">Investigation</div>
            <div><span className="label">Contributing factors (one per line)</span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{(meta?.factor_groups || []).map((g: any) => (
                <div key={g.key}><label className="label" htmlFor={`f-${g.key}`}>{g.label}</label>
                  <textarea id={`f-${g.key}`} className="input" rows={3} disabled={!editable} value={factors[g.key] || ""} onChange={(e) => setFactors({ ...factors, [g.key]: e.target.value })} /></div>))}</div></div>
            <div><span className="label">5 Whys</span><div className="space-y-2">{whys.map((w, n) => (
              <div key={n} className="flex gap-2 items-center"><span className="text-xs w-12" style={{ color: "var(--muted)" }}>Why {n + 1}</span>
                <input className="input" aria-label={`Why ${n + 1}`} disabled={!editable} value={w} onChange={(e) => setWhys(whys.map((x, k) => (k === n ? e.target.value : x)))} /></div>))}</div></div>
            <div><label className="label" htmlFor="root">Root cause statement</label><textarea id="root" className="input" rows={3} disabled={!editable} value={root} onChange={(e) => setRoot(e.target.value)} /></div>
            {editable && <button className="btn" onClick={saveInvestigation}>Save investigation</button>}
          </div>

          <div className="card p-4 text-sm">
            <div className="font-medium mb-1">Corrective and preventive actions</div>
            <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Each completed action needs an effectiveness check: did the fix work?</p>
            {i.capas.length === 0 ? <p style={{ color: "var(--muted)" }}>No actions yet.</p> : (
              <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Action</th><th className="th">Owner</th><th className="th">Due</th><th className="th">Status</th><th className="th">Effectiveness check</th></tr></thead>
                <tbody>{i.capas.map((c: any) => (
                  <tr key={c.id} className={c.overdue ? "bg-red-500/5" : ""}>
                    <td className="td min-w-[16rem]"><Badge k={c.kind === "corrective" ? "amber" : "Triaged"}>{c.kind}</Badge> {c.action}</td><td className="td">{c.owner}</td>
                    <td className="td whitespace-nowrap" style={c.overdue ? { color: "#dc2626", fontWeight: 600 } : {}}>{fmt(c.due_at)}</td>
                    <td className="td"><select className="input !w-36" aria-label="Action status" value={c.status} onChange={(e) => patchCapa(c.id, { status: e.target.value }, "Action updated")}><option>Open</option><option>In progress</option><option>Completed</option></select></td>
                    <td className="td min-w-[11rem]">{c.status !== "Completed" ? <span style={{ color: "var(--muted)" }}>After completion</span> : (
                      <><select className="input" aria-label="Effectiveness" value={c.check_result} onChange={(e) => e.target.value && patchCapa(c.id, { check_result: e.target.value }, "Effectiveness recorded")}>
                        <option value="">Check due {fmt(c.check_due_at)}</option><option value="effective">Effective</option><option value="not_effective">Not effective</option></select>
                        {c.check_overdue && <span className="text-xs text-red-600">Check overdue</span>}{c.check_note && <span className="block text-xs mt-1" style={{ color: "var(--muted)" }}>{c.check_note}</span>}
                        {can(me, "accreditation", "create") && <AttachEvidence sourceType="capa" sourceId={c.id} />}</>)}</td>
                  </tr>))}</tbody></table></div>)}
            {editable && <div className="mt-4 grid grid-cols-1 md:grid-cols-6 gap-2 items-end">
              <div><label className="label" htmlFor="ckind">Type</label><select id="ckind" className="input" value={capa.kind} onChange={(e) => setCapa({ ...capa, kind: e.target.value })}><option value="corrective">Corrective</option><option value="preventive">Preventive</option></select></div>
              <div className="md:col-span-3"><label className="label" htmlFor="cact">New action</label><input id="cact" className="input" value={capa.action} onChange={(e) => setCapa({ ...capa, action: e.target.value })} placeholder="What will be changed?" /></div>
              <div><label className="label" htmlFor="cown">Owner</label><select id="cown" className="input" value={capa.owner_id} onChange={(e) => setCapa({ ...capa, owner_id: e.target.value })}><option value="">Unassigned</option>{(meta?.people || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
              <div><label className="label" htmlFor="cdue">Due date</label><input id="cdue" type="date" className="input" value={capa.due} onChange={(e) => setCapa({ ...capa, due: e.target.value })} /></div>
              <div className="md:col-span-6"><button className="btn" disabled={capa.action.trim().length < 5 || !capa.due} onClick={addCapa}>Add action</button></div></div>}
          </div>
        </div>

        <div className="space-y-4">
          {i.can_triage && <div className="card p-4 space-y-2 text-sm">
            <div className="font-medium">Triage</div>
            <label className="label" htmlFor="tcat">Category</label><select id="tcat" className="input" disabled={closed} value={tri.category} onChange={(e) => setTri({ ...tri, category: e.target.value })}>{meta?.categories.map((c: any) => <option key={c.key} value={c.key}>{c.label}</option>)}</select>
            <label className="label" htmlFor="tharm">Harm level</label><select id="tharm" className="input" disabled={closed} value={tri.harm} onChange={(e) => setTri({ ...tri, harm: e.target.value })}>{meta?.harms.map((c: any) => <option key={c.key} value={c.key}>{c.label}</option>)}</select>
            <label className="label" htmlFor="tinv">Investigator</label><select id="tinv" className="input" disabled={closed} value={tri.investigator_id} onChange={(e) => setTri({ ...tri, investigator_id: e.target.value })}><option value="">Unassigned</option>{meta?.people.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
            <label className="label" htmlFor="tdue">Investigation due</label><input id="tdue" type="date" className="input" disabled={closed} value={tri.due} onChange={(e) => setTri({ ...tri, due: e.target.value })} />
            {!closed && <div className="flex gap-2 pt-1">
              <button className="btn flex-1 justify-center" onClick={() => act(() => api(`/incidents/${i.id}/triage`, { method: "PUT", body: { category: tri.category, harm: tri.harm, investigator_id: tri.investigator_id || null, due_at: tri.due && tri.due !== dateInput(i.due_at) ? dayEnd(tri.due) : null, accept: true } }), "Triage saved")}>{i.status === "Reported" ? "Accept and save" : "Save triage"}</button></div>}
          </div>}
          {i.can_triage && <div className="card p-4 space-y-2 text-sm">
            <div className="font-medium">Decisions</div>
            {i.sentinel && !i.escalated_at && !closed && <button className="btn btn-danger w-full justify-center" onClick={() => act(() => api(`/incidents/${i.id}/escalate`, { body: {} }), "Escalated to management")}>Escalate to management</button>}
            {!closed ? <button className="btn btn-ghost w-full justify-center" onClick={() => act(() => api(`/incidents/${i.id}/status`, { body: { status: "Closed" } }), "Incident closed")}>Close incident</button>
              : <button className="btn btn-ghost w-full justify-center" onClick={() => act(() => api(`/incidents/${i.id}/status`, { body: { status: "Under investigation" } }), "Incident reopened")}>Reopen</button>}
            {err && <p className="text-xs text-red-600">{err}</p>}
            <p className="text-xs" style={{ color: "var(--muted)" }}>Closing needs a root cause. Moderate and serious incidents also need an action, and serious events must be escalated first.</p>
          </div>}
          <div className="card p-4 text-sm">
            <div className="font-medium mb-3">Timeline</div>
            <ol className="space-y-3">{i.timeline.map((e: any) => (
              <li key={e.id} className="border-s-2 ps-3" style={{ borderColor: e.kind === "fact" ? "#94a3b8" : "var(--brand)" }}>
                <div><span className="text-[11px] uppercase tracking-wide me-2" style={{ color: "var(--muted)" }}>{KIND[e.kind] || e.kind}</span>{e.text}</div>
                <div className="text-xs" style={{ color: "var(--muted)" }}>{e.actor} · {fmt(e.at)}</div></li>))}</ol>
            {editable && <div className="mt-4 space-y-2"><label className="label" htmlFor="fat">Add a fact to the timeline</label>
              <input id="fat" type="datetime-local" className="input" value={fact.at} onChange={(e) => setFact({ ...fact, at: e.target.value })} />
              <input className="input" aria-label="What happened" placeholder="What happened at that time?" value={fact.text} onChange={(e) => setFact({ ...fact, text: e.target.value })} />
              <button className="btn btn-ghost w-full justify-center" disabled={fact.text.trim().length < 3} onClick={() => act(async () => { await api(`/incidents/${i.id}/facts`, { body: { at: toIso(fact.at), text: fact.text } }); setFact({ at: localInput(), text: "" }); }, "Added to timeline")}>Add to timeline</button></div>}
          </div>
        </div>
      </div>
    </>
  );
}

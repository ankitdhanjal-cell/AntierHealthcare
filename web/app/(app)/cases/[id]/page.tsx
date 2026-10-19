"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { AiTag, Badge, ErrorBox, PageHead, Skeleton, fmt, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

export default function CaseView() {
  const { id } = useParams<{ id: string }>(); const me = useMe(); const toast = useToast(); const router = useRouter();
  const { data: c, loading, error, reload } = useFetch<any>(`/cases/${id}`);
  const users = useFetch<any[]>(can(me, "users") ? "/users" : null);
  const [note, setNote] = useState(""); const [res, setRes] = useState(""); const [err, setErr] = useState("");
  const [callOutcome, setCallOutcome] = useState("reached"); const [callNote, setCallNote] = useState("");
  if (loading) return <Skeleton rows={6} />;
  if (error || !c) return <ErrorBox msg={error} retry={reload} />;
  const act = async (fn: () => Promise<any>, ok: string) => { setErr(""); try { await fn(); toast(ok); reload(); } catch (e: any) { setErr(e.message); toast(e.message, "err"); } };
  const canEdit = can(me, "cases", "create");
  return (
    <>
      <PageHead title={`${c.number} · ${c.title}`} sub={`${c.department} · patient ${c.patient}`}>
        {c.incident && <Link href={`/quality/incidents/${c.incident.id}`} className="btn btn-ghost">Incident {c.incident.number}</Link>}
        {!c.incident && canEdit && can(me, "incidents", "create") && <button className="btn btn-ghost" onClick={() => act(async () => { const r = await api(`/cases/${id}/raise-incident`, { body: {} }); router.push(`/quality/incidents/${r.incident_id}`); }, "Incident raised")}>Raise incident</button>}
        <Badge k={c.urgency} /><Badge k={c.status} />{c.overdue && <Badge k="Overdue" />}{c.loop_closed && <Badge k="green">Loop closed</Badge>}
      </PageHead>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          {c.feedback && <div className="card p-4"><div className="font-medium text-sm mb-2">Original feedback ({c.feedback.rating}/5) <AiTag /></div>
            <p className="text-sm" dir={c.feedback.language === "ar" ? "rtl" : "ltr"}>{c.feedback.text || "No comment."}</p>
            {c.feedback.translation && c.feedback.language === "ar" && <p className="text-sm mt-2" style={{ color: "var(--muted)" }}>Translation: {c.feedback.translation}</p>}
            <Link className="text-xs underline" href={`/feedback/${c.feedback.id}`}>Open feedback detail</Link></div>}
          <div className="card p-4">
            <div className="font-medium text-sm mb-3">Timeline</div>
            <ol className="space-y-3">{c.timeline.map((e: any, i: number) => <li key={i} className="text-sm border-s-2 ps-3" style={{ borderColor: "var(--brand)" }}><div>{e.text}</div><div className="text-xs" style={{ color: "var(--muted)" }}>{e.actor} · {fmt(e.at)}</div></li>)}</ol>
            {canEdit && <div className="mt-4 flex gap-2"><input className="input" placeholder="Add a note…" value={note} onChange={(e) => setNote(e.target.value)} />
              <button className="btn" onClick={() => act(async () => { await api(`/cases/${id}/notes`, { body: { text: note } }); setNote(""); }, "Note added")}>Add note</button></div>}
          </div>
        </div>
        <div className="space-y-4">
          <div className="card p-4 text-sm space-y-2">
            <div><span className="label">Owner</span>{c.owner}</div>
            <div><span className="label">Due (SLA {c.sla_hours}h, {c.urgency})</span><span style={c.overdue ? { color: "#dc2626", fontWeight: 600 } : {}}>{fmt(c.due_at)}</span></div>
            {c.resolution && <div><span className="label">Resolution</span>{c.resolution}</div>}
            {can(me, "cases", "approve") && users.data && <div><label className="label">Reassign</label>
              <select className="input" value="" onChange={(e) => e.target.value && act(() => api(`/cases/${id}/assign`, { body: { owner_id: e.target.value } }), "Case reassigned")}><option value="">Choose a user…</option>{users.data.filter((u) => u.active).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></div>}
          </div>
          {canEdit && <div className="card p-4 space-y-2 text-sm">
            <div className="font-medium">Call patient</div>
            <p className="text-xs" style={{ color: "var(--muted)" }}>Record what happened on the call-back. It is added to the timeline.</p>
            <label className="label" htmlFor="call-outcome">Outcome</label>
            <select id="call-outcome" className="input" value={callOutcome} onChange={(e) => setCallOutcome(e.target.value)}>
              <option value="reached">Patient reached</option><option value="apologised">Apologised to patient</option><option value="resolved">Resolved on the call</option><option value="follow_up">Follow-up needed</option><option value="no_answer">No answer</option></select>
            <textarea className="input" rows={2} placeholder="Notes (optional)" value={callNote} onChange={(e) => setCallNote(e.target.value)} />
            <button className="btn w-full justify-center" onClick={() => act(async () => { await api(`/cases/${id}/call`, { body: { outcome: callOutcome, note: callNote } }); setCallNote(""); }, "Call logged")}>Log call</button>
            {(c.status === "Resolved" || c.status === "Closed") && (c.closing_message_at ? <p className="text-xs" style={{ color: "var(--muted)" }}>Closing message sent {fmt(c.closing_message_at)}.</p> :
              <button className="btn btn-ghost w-full justify-center" onClick={() => act(() => api(`/cases/${id}/closing-message`, { body: {} }), "Closing message sent")}>Send closing message to the patient</button>)}
          </div>}
          {canEdit && c.status !== "Closed" && <div className="card p-4 space-y-2 text-sm">
            <div className="font-medium">Update status</div>
            {["Assigned", "In investigation"].filter((s) => s !== c.status).map((s) => <button key={s} className="btn btn-ghost w-full justify-center" onClick={() => act(() => api(`/cases/${id}/status`, { body: { status: s } }), `Status: ${s}`)}>Move to {s}</button>)}
            <label className="label mt-2">Resolution note</label>
            <textarea className="input" rows={3} value={res} onChange={(e) => setRes(e.target.value)} />
            {err && <p className="text-xs text-red-600">{err}</p>}
            <div className="flex gap-2"><button className="btn flex-1 justify-center" onClick={() => act(() => api(`/cases/${id}/status`, { body: { status: "Resolved", resolution: res } }), "Case resolved")}>Resolve</button>
              <button className="btn btn-ghost flex-1 justify-center" onClick={() => act(() => api(`/cases/${id}/status`, { body: { status: "Closed", resolution: res } }), "Case closed")}>Close</button></div>
          </div>}
        </div>
      </div>
    </>
  );
}

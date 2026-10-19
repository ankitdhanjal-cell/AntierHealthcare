"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Badge, ErrorBox, PageHead, PctBar, Skeleton, fmt, fmtDate, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

const rag = (p: number) => (p >= 85 ? "#0f9d6b" : p >= 65 ? "#d97706" : "#dc4a3d");

export default function Accreditation() {
  const me = useMe(); const toast = useToast(); const router = useRouter();
  const { data, loading, error, reload } = useFetch<any>("/accreditation/summary");
  const runs = useFetch<any[]>("/accreditation/tracers");
  const [date, setDate] = useState("");
  if (loading) return <><PageHead title="Accreditation readiness" /><Skeleton rows={6} /></>;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  const r = data.readiness;
  const startTracer = async (cid: string) => { const t = await api("/accreditation/tracers", { body: { chapter_id: cid } }); router.push(`/quality/accreditation/tracer/${t.id}`); };
  return (
    <>
      <PageHead title="Accreditation readiness" sub={`${data.name} · sample standards library`} />
      {!me.sees_all && <p className="text-xs mb-3" style={{ color: "var(--muted)" }}>Readiness covers the whole hospital, not only your department.</p>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div className="card p-4"><div className="text-xs" style={{ color: "var(--muted)" }}>Overall readiness</div>
          <div className="text-3xl font-semibold mt-1" style={{ color: rag(r.pct) }}>{r.pct}%</div>
          <div className="my-2"><PctBar pct={r.pct} color={rag(r.pct)} /></div>
          <div className="text-xs" style={{ color: "var(--muted)" }}>{r.met} of {r.applicable} applicable elements met</div></div>
        <div className="card p-4"><div className="text-xs" style={{ color: "var(--muted)" }}>Survey countdown</div>
          <div className="text-3xl font-semibold mt-1">{data.days_left == null ? "Not set" : data.days_left < 0 ? "Survey date passed" : `${data.days_left} days`}</div>
          <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>{data.survey_date ? `Survey on ${fmtDate(data.survey_date)}` : "Set the survey date to start the countdown."}</div>
          {can(me, "accreditation", "approve") && <div className="mt-2 flex gap-2"><input type="date" className="input" aria-label="Survey date" value={date || data.survey_date || ""} onChange={(e) => setDate(e.target.value)} />
            <button className="btn btn-ghost" disabled={!date} onClick={async () => { try { await api("/accreditation/survey-date", { method: "PUT", body: { survey_date: date } }); toast("Survey date saved"); setDate(""); reload(); } catch (e: any) { toast(e.message, "err"); } }}>Save</button></div>}</div>
        <div className="card p-4"><div className="text-xs mb-2" style={{ color: "var(--muted)" }}>Elements by status</div>
          <ul className="space-y-1 text-sm">{Object.entries(r.counts).map(([k, v]: any) => <li key={k} className="flex justify-between"><Link className="underline" href={`/quality/accreditation/elements?status=${encodeURIComponent(k)}`}><Badge k={k} /></Link><span className="tabular-nums">{v}</span></li>)}</ul>
          {data.met_without_evidence > 0 && <p className="text-xs mt-2 text-amber-700">{data.met_without_evidence} met elements have no evidence attached.</p>}</div>
      </div>
      <div className="card mb-4">
        <div className="p-4 flex justify-between items-center"><h2 className="font-medium text-sm">Readiness by chapter</h2><Link className="text-xs underline" href="/quality/accreditation/elements">All elements</Link></div>
        <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Chapter</th><th className="th w-56">Met</th><th className="th">Met / applicable</th><th className="th">Partly</th><th className="th">Not met</th><th className="th">Mock survey</th></tr></thead>
          <tbody>{data.chapters.map((c: any) => (
            <tr key={c.id}><td className="td"><Link className="underline font-medium" href={`/quality/accreditation/chapters/${c.id}`}>{c.code}</Link> {c.name}</td>
              <td className="td"><div className="flex items-center gap-2"><div className="flex-1"><PctBar pct={c.pct} color={rag(c.pct)} /></div><span className="w-12 text-end tabular-nums text-sm">{c.pct}%</span></div></td>
              <td className="td tabular-nums">{c.met} / {c.applicable}</td><td className="td tabular-nums">{c.counts["Partially met"]}</td><td className="td tabular-nums">{c.counts["Not met"]}</td>
              <td className="td">{can(me, "accreditation", "create") && <button className="btn btn-ghost" onClick={() => startTracer(c.id)}>Start mock survey</button>}</td></tr>))}</tbody></table></div>
      </div>
      <div className="card mb-4">
        <div className="p-4"><h2 className="font-medium text-sm">Open gaps</h2><p className="text-xs" style={{ color: "var(--muted)" }}>Elements that are not met or partially met, with the owner and any follow-up actions.</p></div>
        {data.gaps.length === 0 ? <p className="px-4 pb-4 text-sm" style={{ color: "var(--muted)" }}>No open gaps.</p> : (
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Element</th><th className="th">Status</th><th className="th">Owner</th><th className="th">Open actions</th><th className="th">Reviewed</th></tr></thead>
            <tbody>{data.gaps.map((g: any) => (
              <tr key={g.id}><td className="td min-w-[18rem]"><Link className="underline font-medium" href={`/quality/accreditation/elements/${g.id}`}>{g.code}</Link> {g.text}<span className="block text-xs" style={{ color: "var(--muted)" }}>{g.note}</span></td>
                <td className="td"><Badge k={g.status} /></td><td className="td">{g.owner}</td><td className="td tabular-nums">{g.open_actions}</td><td className="td whitespace-nowrap">{fmtDate(g.last_reviewed_at)}</td></tr>))}</tbody></table></div>)}
      </div>
      <div className="card">
        <div className="p-4"><h2 className="font-medium text-sm">Recent mock surveys</h2></div>
        {!runs.data?.length ? <p className="px-4 pb-4 text-sm" style={{ color: "var(--muted)" }}>No mock surveys yet. Start one from the chapter table above.</p> :
          <table className="w-full"><thead><tr><th className="th">Chapter</th><th className="th">By</th><th className="th">Started</th><th className="th">Status</th></tr></thead>
            <tbody>{runs.data.map((t) => <tr key={t.id}><td className="td"><Link className="underline" href={`/quality/accreditation/tracer/${t.id}`}>{t.chapter}</Link></td><td className="td">{t.started_by}</td><td className="td">{fmt(t.started_at)}</td><td className="td">{t.completed_at ? <Badge k="Completed" /> : <Badge k="In progress" />}</td></tr>)}</tbody></table>}
      </div>
    </>
  );
}

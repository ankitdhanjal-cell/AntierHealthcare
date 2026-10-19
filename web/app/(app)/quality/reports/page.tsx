"use client";
import { useState } from "react";
import { api, getToken } from "@/lib/api";
import { Badge, ErrorBox, PageHead, Skeleton, fmt, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

export default function Reports() {
  const me = useMe(); const toast = useToast();
  const list = useFetch<any[]>("/reports/committee");
  const [period, setPeriod] = useState("");
  const p = period || list.data?.[0]?.period || "";
  const prev = useFetch<any>(p ? `/reports/committee/${p}` : null, [p]);
  const [note, setNote] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  if (list.loading) return <><PageHead title="Committee reports" /><Skeleton rows={5} /></>;
  if (list.error || !list.data) return <ErrorBox msg={list.error} retry={list.reload} />;
  const canEdit = can(me, "reports", "create");
  const download = async () => {
    setBusy(true);
    try {
      if (note !== null && canEdit) await api(`/reports/committee/${p}/note`, { method: "PUT", body: { cover_note: note } });
      const r = await fetch(`/api/reports/committee/${p}/pdf`, { headers: { authorization: `Bearer ${getToken()}` } });
      if (!r.ok) throw new Error((await r.json()).detail || "Could not build the pack");
      const url = URL.createObjectURL(await r.blob()); const a = document.createElement("a"); a.href = url; a.download = `committee-pack-${p}.pdf`; a.click(); URL.revokeObjectURL(url);
      toast("Committee pack downloaded"); list.reload();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const d = prev.data;
  return (
    <>
      <PageHead title="Committee reports" sub="The monthly Quality and Patient Safety Committee pack, built from live records as a branded PDF" />
      <div className="card p-3 mb-4 flex flex-wrap items-center gap-3">
        <label className="label !mb-0" htmlFor="rp">Month</label>
        <select id="rp" className="input !w-52" value={p} onChange={(e) => { setPeriod(e.target.value); setNote(null); }}>{list.data.map((x) => <option key={x.period} value={x.period}>{x.label}</option>)}</select>
        <button className="btn ms-auto" disabled={busy || !p} onClick={download}>{busy ? "Building PDF…" : "Download committee pack (PDF)"}</button>
      </div>
      {prev.loading && !d ? <Skeleton rows={5} /> : prev.error || !d ? <ErrorBox msg={prev.error} retry={prev.reload} /> : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-4">
            <div className="card p-4 text-sm space-y-2"><h2 className="font-medium">Cover note</h2>
              <p className="text-xs" style={{ color: "var(--muted)" }}>Appears on the cover page. Leave a blank line between paragraphs.</p>
              <label className="label" htmlFor="cn">Note from the Quality Manager</label>
              <textarea id="cn" className="input" rows={6} disabled={!canEdit} value={note ?? d.cover_note} onChange={(e) => setNote(e.target.value)} placeholder="Summarise the month for the committee: what improved, what needs a decision." />
              {canEdit && <button className="btn btn-ghost" disabled={note === null} onClick={async () => { try { await api(`/reports/committee/${p}/note`, { method: "PUT", body: { cover_note: note } }); toast("Cover note saved"); setNote(null); prev.reload(); list.reload(); } catch (e: any) { toast(e.message, "err"); } }}>Save note</button>}</div>
            <div className="card overflow-x-auto"><div className="p-4"><h2 className="font-medium text-sm">What the pack will show</h2></div>
              <table className="w-full"><thead><tr><th className="th">Indicator</th><th className="th">Result</th><th className="th">Target</th><th className="th">Status</th></tr></thead>
                <tbody>{d.kpis.map((k: any) => <tr key={k.name}><td className="td">{k.name}</td><td className="td tabular-nums">{k.value}</td><td className="td tabular-nums">{k.target}</td><td className="td">{k.rag === "neutral" ? "—" : <Badge k={k.rag}>{k.rag === "green" ? "On target" : k.rag === "amber" ? "Watch" : "Off target"}</Badge>}</td></tr>)}</tbody></table></div>
          </div>
          <div className="space-y-4 text-sm">
            <div className="card p-4 space-y-1.5"><h2 className="font-medium mb-1">Also included</h2>
              <p>{d.charts} run charts with median and target</p><p>{d.themes.length} complaint themes for {d.label}</p><p>{d.incident_total} incidents by harm level and category{d.serious ? `, ${d.serious} serious` : ""}</p>
              <p>{d.overdue_actions} overdue corrective actions</p><p>{d.audits.length} audit types with compliance, {d.overdue_audits} audits overdue</p>
              <p>Accreditation readiness: {d.readiness.pct}%{d.survey ? `, survey in ${d.survey.days_left} days` : ""}</p></div>
            {list.data.find((x) => x.period === p)?.generated_at && <p className="text-xs" style={{ color: "var(--muted)" }}>Last exported {fmt(list.data.find((x) => x.period === p).generated_at)} by {list.data.find((x) => x.period === p).generated_by}.</p>}
          </div>
        </div>)}
    </>
  );
}

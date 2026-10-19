"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Empty, ErrorBox, PageHead, Skeleton, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";

const lastMonth = () => { const d = new Date(); d.setMonth(d.getMonth() - 1); return d.toLocaleDateString("en-CA").slice(0, 7); };

export default function Entry() {
  const toast = useToast();
  const [period, setPeriod] = useState(lastMonth());
  const { data, loading, error, reload } = useFetch<any[]>(`/indicators/entry?period=${period}`, [period]);
  const [vals, setVals] = useState<Record<string, any>>({});
  const get = (r: any, k: string) => vals[r.id]?.[k] ?? (r[k] ?? "");
  const set = (id: string, k: string, v: string) => setVals({ ...vals, [id]: { ...vals[id], [k]: v } });
  const save = async (r: any) => {
    try { const x = await api(`/indicators/${r.id}/values`, { method: "PUT", body: { period, numerator: Number(get(r, "numerator")), denominator: Number(get(r, "denominator")), note: get(r, "note") } });
      toast(`${r.name}: ${x.value} ${r.unit}`); setVals({ ...vals, [r.id]: undefined as any }); reload(); } catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <>
      <PageHead title="Monthly indicator entry" sub="Values for indicators that are not calculated from records. The rate is worked out from the numerator and denominator." />
      <div className="card p-3 mb-4 flex items-center gap-3"><label className="label !mb-0" htmlFor="per">Month</label><input id="per" type="month" className="input !w-44" value={period} max={new Date().toLocaleDateString("en-CA").slice(0, 7)} onChange={(e) => setPeriod(e.target.value)} /></div>
      {loading ? <Skeleton rows={5} /> : error || !data ? <ErrorBox msg={error} retry={reload} /> : data.length === 0 ? <Empty title="No manual indicators" hint="All indicators are calculated from records." /> : (
        <div className="space-y-3">{data.map((r) => (
          <div key={r.id} className="card p-4 text-sm">
            <div className="flex flex-wrap justify-between gap-2 mb-2"><div><b>{r.name}</b><span className="block text-xs" style={{ color: "var(--muted)" }}>Target {r.target} {r.unit} · owner {r.owner}</span></div>
              <div className="tabular-nums font-semibold">{r.value != null && vals[r.id] === undefined ? `${r.value} ${r.unit}` : ""}</div></div>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-2 items-end">
              <div className="md:col-span-1"><label className="label" htmlFor={`n-${r.id}`}>{r.numerator_label}</label><input id={`n-${r.id}`} type="number" min={0} step="any" className="input" value={get(r, "numerator")} onChange={(e) => set(r.id, "numerator", e.target.value)} /></div>
              <div><label className="label" htmlFor={`d-${r.id}`}>{r.denominator_label}</label><input id={`d-${r.id}`} type="number" min={0} step="any" className="input" value={get(r, "denominator")} onChange={(e) => set(r.id, "denominator", e.target.value)} /></div>
              <div className="md:col-span-2"><label className="label" htmlFor={`o-${r.id}`}>Note (optional)</label><input id={`o-${r.id}`} className="input" value={get(r, "note")} onChange={(e) => set(r.id, "note", e.target.value)} /></div>
              <button className="btn" disabled={get(r, "numerator") === "" || !Number(get(r, "denominator"))} onClick={() => save(r)}>Save</button></div>
          </div>))}</div>)}
    </>
  );
}

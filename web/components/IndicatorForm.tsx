"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "./ui";
import { useToast } from "./Providers";

/** Add or edit a quality indicator: the definition fields a quality professional expects. */
export function IndicatorForm({ ind, onDone, onCancel }: { ind?: any; onDone: () => void; onCancel: () => void }) {
  const toast = useToast();
  const users = useFetch<any[]>("/users");
  const [f, setF] = useState<any>(ind ? { ...ind } : { key: "", name: "", definition: "", numerator: "", denominator: "", multiplier: 100, unit: "%", target: "", amber: "", direction: "higher", frequency: "Monthly", source: "", owner_id: "" });
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const save = async () => {
    try {
      const body = { name: f.name, definition: f.definition, numerator: f.numerator, denominator: f.denominator, unit: f.unit, target: Number(f.target), amber: f.amber === "" || f.amber == null ? null : Number(f.amber),
        frequency: f.frequency, source: f.source, owner_id: f.owner_id || null };
      if (ind) await api(`/indicators/${ind.id}`, { method: "PUT", body });
      else await api("/indicators", { body: { ...body, key: f.key, multiplier: Number(f.multiplier), direction: f.direction } });
      toast(ind ? "Indicator saved" : "Indicator added"); onDone();
    } catch (e: any) { toast(e.message, "err"); }
  };
  const Field = ({ k, label, wide, type = "text" }: any) => <div className={wide ? "md:col-span-2" : ""}><label className="label" htmlFor={`if-${k}`}>{label}</label><input id={`if-${k}`} type={type} step="any" className="input" value={f[k] ?? ""} onChange={(e) => set(k, e.target.value)} /></div>;
  return (
    <div className="card p-4 mb-4 text-sm">
      <h2 className="font-medium mb-3">{ind ? "Edit indicator" : "New indicator"}</h2>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        {!ind && <Field k="key" label="Short key (letters, numbers, underscore)" />}
        <Field k="name" label="Name" wide />
        <Field k="definition" label="Definition" wide />
        <Field k="numerator" label="Numerator" wide /><Field k="denominator" label="Denominator" wide />
        {!ind && <><Field k="multiplier" label="Multiply by (100 for %, 1000 for per 1,000)" type="number" />
          <div><label className="label" htmlFor="if-dir">Better when</label><select id="if-dir" className="input" value={f.direction} onChange={(e) => set("direction", e.target.value)}><option value="higher">Higher</option><option value="lower">Lower</option></select></div></>}
        <Field k="unit" label="Unit" /><Field k="target" label="Target" type="number" /><Field k="amber" label="Watch level" type="number" /><Field k="frequency" label="Frequency" />
        <Field k="source" label="Data source" wide />
        <div><label className="label" htmlFor="if-own">Owner</label><select id="if-own" className="input" value={f.owner_id || ""} onChange={(e) => set("owner_id", e.target.value)}><option value="">Unassigned</option>{(users.data || []).filter((u) => u.active).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select></div>
      </div>
      <div className="flex gap-2 mt-4"><button className="btn" disabled={!f.name || !f.definition || !f.numerator || !f.denominator || f.target === "" || (!ind && !f.key)} onClick={save}>Save</button><button className="btn btn-ghost" onClick={onCancel}>Cancel</button></div>
    </div>
  );
}

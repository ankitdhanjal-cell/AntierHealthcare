"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { ErrorBox, PageHead, Skeleton, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";

function Editor({ t, done }: { t: any; done: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({ name: t.name, description: t.description, items: t.items.map((i: any) => i.text).join("\n"), target: t.target, active: t.active });
  const save = async () => {
    try {
      const body = { ...f, items: f.items.split("\n"), target: Number(f.target) };
      t.id ? await api(`/audits/templates/${t.id}`, { method: "PUT", body }) : await api("/audits/templates", { body });
      toast("Template saved"); done();
    } catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <div className="card p-4 space-y-2 text-sm">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-2"><div className="md:col-span-3"><label className="label" htmlFor={`n-${t.id}`}>Name</label><input id={`n-${t.id}`} className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
        <div><label className="label" htmlFor={`t-${t.id}`}>Target compliance %</label><input id={`t-${t.id}`} type="number" min={1} max={100} className="input" value={f.target} onChange={(e) => setF({ ...f, target: e.target.value as any })} /></div></div>
      <label className="label" htmlFor={`d-${t.id}`}>Description</label><input id={`d-${t.id}`} className="input" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
      <label className="label" htmlFor={`i-${t.id}`}>Checklist (one question per line)</label><textarea id={`i-${t.id}`} className="input" rows={Math.min(14, f.items.split("\n").length + 1)} value={f.items} onChange={(e) => setF({ ...f, items: e.target.value })} />
      <label className="flex items-center gap-1.5"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /> Active</label>
      <button className="btn" onClick={save}>Save template</button>
    </div>
  );
}

export default function Templates() {
  const { data, loading, error, reload } = useFetch<any[]>("/audits/templates");
  const [adding, setAdding] = useState(false);
  if (loading) return <Skeleton rows={4} />;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  return (
    <>
      <PageHead title="Audit templates" sub="Edit the checklists and compliance targets. Existing results keep their wording.">
        <button className="btn" onClick={() => setAdding(!adding)}>{adding ? "Cancel" : "New template"}</button></PageHead>
      <div className="space-y-4 max-w-3xl">
        {adding && <Editor t={{ id: "", name: "", description: "", items: [], target: 90, active: true }} done={() => { setAdding(false); reload(); }} />}
        {data.map((t) => <Editor key={t.id} t={t} done={reload} />)}</div>
    </>
  );
}

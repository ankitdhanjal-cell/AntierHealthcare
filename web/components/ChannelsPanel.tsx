"use client";
import { useEffect, useState } from "react";
import { api, getToken } from "@/lib/api";
import { Badge, ErrorBox, Skeleton, useFetch } from "./ui";
import { useToast } from "./Providers";

function QrImage({ id, name }: { id: string; name: string }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let url = "";
    fetch(`/api/channels/${id}/qr.svg`, { headers: { authorization: `Bearer ${getToken()}` } }).then((r) => r.blob()).then((b) => { url = URL.createObjectURL(b); setSrc(url); }).catch(() => {});
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [id]);
  return src ? <img src={src} alt={`QR code for ${name}`} className="w-40 h-40 bg-white p-1 rounded" /> : <div className="w-40 h-40 skeleton" />;
}

/** Printable QR codes for each ward and clinic. Scanning one opens the same bilingual form patients get after discharge. */
export function ChannelsPanel({ edit }: { edit: boolean }) {
  const toast = useToast();
  const list = useFetch<any[]>("/channels");
  const meta = useFetch<any>("/incidents/meta");
  const [f, setF] = useState({ name: "", kind: "ward", department_id: "" });
  if (list.loading) return <Skeleton rows={4} />;
  if (list.error || !list.data) return <ErrorBox msg={list.error} retry={list.reload} />;
  const add = async () => { try { await api("/channels", { body: { ...f, department_id: f.department_id || null } }); toast("QR code created"); setF({ ...f, name: "" }); list.reload(); } catch (e: any) { toast(e.message, "err"); } };
  const toggle = (c: any) => api(`/channels/${c.id}`, { method: "PUT", body: { name: c.name, kind: c.kind, department_id: c.department_id, active: !c.active } }).then(() => { toast(c.active ? "QR code switched off" : "QR code switched on"); list.reload(); }).catch((e) => toast(e.message, "err"));
  return (
    <div className="space-y-4">
      <div className="card p-4 text-sm no-print flex flex-wrap justify-between gap-3 items-center">
        <p className="max-w-2xl" style={{ color: "var(--muted)" }}>Print a QR code for each ward and clinic. Patients and visitors scan it and open the same English and Arabic form. Patients without WhatsApp can be sent a short SMS with the same link from Integrations.</p>
        <button className="btn" onClick={() => window.print()}>Print all QR codes</button></div>
      {edit && <div className="card p-4 grid grid-cols-1 md:grid-cols-5 gap-2 items-end no-print">
        <div className="md:col-span-2"><label className="label" htmlFor="chn">Ward or clinic name</label><input id="chn" className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Ward 5 visitors' lounge" /></div>
        <div><label className="label" htmlFor="chk">Type</label><select id="chk" className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="ward">Ward</option><option value="clinic">Clinic</option></select></div>
        <div><label className="label" htmlFor="chd">Department</label><select id="chd" className="input" value={f.department_id} onChange={(e) => setF({ ...f, department_id: e.target.value })}><option value="">Choose…</option>{meta.data?.departments.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
        <button className="btn" disabled={f.name.trim().length < 2} onClick={add}>Add QR code</button></div>}
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">{list.data.map((c) => (
        <div key={c.id} className="card p-4 text-center" style={c.active ? {} : { opacity: 0.55 }}>
          <div className="flex justify-center"><QrImage id={c.id} name={c.name} /></div>
          <div className="font-semibold mt-2">{c.name}</div>
          <div className="text-sm">Scan to tell us about your visit</div><div className="text-sm" dir="rtl">امسح الرمز لمشاركة رأيك في زيارتك</div>
          <div className="text-xs mt-2 flex justify-center gap-2 items-center no-print" style={{ color: "var(--muted)" }}><Badge k="neutral">{c.kind}</Badge>{c.department} · {c.responses} responses{!c.active && " · off"}</div>
          {edit && <button className="text-xs underline mt-2 no-print" onClick={() => toggle(c)}>{c.active ? "Switch off" : "Switch on"}</button>}
        </div>))}</div>
    </div>
  );
}

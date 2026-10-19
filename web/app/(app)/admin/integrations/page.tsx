"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Badge, PageHead, Skeleton, fmt, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";
import { PatientPreviewPair } from "@/components/PatientPreview";

export default function Integrations() {
  const me = useMe(); const toast = useToast();
  const cards = useFetch<any[]>("/integrations");
  const patients = useFetch<any[]>("/integrations/his/patients");
  const [open, setOpen] = useState<string | null>(null);
  const [pid, setPid] = useState(""); const [now, setNow] = useState(true); const [log, setLog] = useState<any[]>([]);
  const [msgs, setMsgs] = useState<any[]>([]); const [busy, setBusy] = useState(false);
  const [watch, setWatch] = useState<string>(""); const [token, setToken] = useState(""); const [channel, setChannel] = useState("whatsapp"); const [showPatient, setShowPatient] = useState(false);
  const chat = useRef<HTMLDivElement>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const load = () => api<any[]>("/whatsapp/messages" + (watch ? `?patient_id=${watch}` : "")).then(setMsgs).catch(() => {});
    load(); const i = setInterval(load, 3000); return () => clearInterval(i);
  }, [watch, tick]);
  useEffect(() => { chat.current?.scrollTo(0, 99999); }, [msgs]);
  const send = async () => {
    setBusy(true);
    try { const r = await api("/integrations/his/discharge", { body: { patient_id: pid, send_now: now, channel } });
      setLog((l) => [{ at: fmt(new Date().toISOString()), hl7: r.hl7, status: r.status }, ...l]);
      setWatch(pid); setTick((t) => t + 1); toast(now ? `Discharge event received; ${channel === "sms" ? "SMS" : "WhatsApp message"} sent` : "Discharge event received; feedback request queued"); setToken(""); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const cur = msgs.length ? msgs[msgs.length - 1] : null;
  return (
    <>
      <PageHead title="Integrations" sub="Connectors to external systems. Sandbox connectors run on sample data." />
      {cards.loading ? <Skeleton /> : <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">{cards.data?.map((c) => (
        <div key={c.key} className="card p-4 flex flex-col gap-2"><div className="flex justify-between"><b className="text-sm">{c.name}</b><Badge k={c.status} /></div>
          <p className="text-xs flex-1" style={{ color: "var(--muted)" }}>{c.desc}</p>
          {c.key === "his" ? <button className="btn" onClick={() => setOpen(open === "his" ? null : "his")}>Open event console</button> :
            c.key === "whatsapp" ? <button className="btn btn-ghost" onClick={() => setOpen("his")}>View phone preview</button> :
            <button className="btn btn-ghost" onClick={() => toast(`${c.name}: configuration is available when you connect your account. Contact support to enable.`)}>Configure</button>}
        </div>))}</div>}
      {open === "his" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card p-4 space-y-3">
            <h2 className="font-medium">HIS event console (Sandbox)</h2>
            <label className="label" htmlFor="pt">Patient</label>
            <select id="pt" className="input" value={pid} onChange={(e) => setPid(e.target.value)}><option value="">Select a patient…</option>{patients.data?.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.mrn} · {p.language === "ar" ? "Arabic" : "English"}</option>)}</select>
            <label className="label" htmlFor="ch">Send the feedback request by</label>
            <select id="ch" className="input" value={channel} onChange={(e) => setChannel(e.target.value)}><option value="whatsapp">WhatsApp</option><option value="sms">SMS (short text, same link)</option></select>
            <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={now} onChange={(e) => setNow(e.target.checked)} /> Send now (otherwise queued with the configured delay)</label>
            {can(me, "integrations", "create") && <button className="btn" disabled={!pid || busy} onClick={send}>{busy ? "Sending…" : "Send discharge event (ADT^A03)"}</button>}
            <div className="space-y-2">{log.map((l, i) => <pre key={i} className="text-xs p-2 rounded overflow-auto" style={{ background: "var(--line)" }}>{l.at} · {l.status}{"\n"}{l.hl7}</pre>)}</div>
          </div>
          <div className="mx-auto w-[320px]">
            <div className="rounded-[2rem] border-8 border-slate-800 bg-white overflow-hidden shadow-xl text-slate-900" style={{ height: 620 }}>
              <div className="bg-[#075e54] text-white px-4 py-2 text-sm font-medium">{cur?.patient ? `WhatsApp · ${cur.patient}` : "WhatsApp (sandbox)"}</div>
              {!token && <div ref={chat} className="p-3 space-y-2 overflow-auto bg-[#ece5dd]" style={{ height: 540 }}>
                {msgs.length === 0 && <p className="text-xs text-center mt-8 text-slate-500">Send a discharge event to see the feedback message here.</p>}
                {msgs.map((m) => (
                  <div key={m.id} className="bg-white rounded-lg p-2.5 text-sm max-w-[90%] shadow-sm" dir={m.language === "ar" ? "rtl" : "ltr"}>
                    <div className="whitespace-pre-line">{m.body}</div>
                    {m.link && <button className="mt-2 text-[#0a7cff] underline text-xs break-all" onClick={() => setToken(m.link.split("/f/")[1])}>{m.link}</button>}
                    <div className="text-[10px] text-slate-400 text-end mt-1">{m.channel === "sms" && <b className="me-1">SMS</b>}{fmt(m.created_at)}</div></div>))}
              </div>}
              {token && <div style={{ height: 540 }} className="overflow-auto"><iframe title="Patient feedback form" src={`/f/${token}`} className="w-full h-full border-0" /></div>}
            </div>
            {token && <button className="btn btn-ghost w-full justify-center mt-2" onClick={() => setToken("")}>Back to chat</button>}
          </div>
        </div>
      )}
      <div className="card p-4 mt-6">
        <div className="flex justify-between items-center"><div><h2 className="font-medium text-sm">What the patient sees</h2><p className="text-xs" style={{ color: "var(--muted)" }}>The message and the form on a phone, in English and Arabic. Switch language on the form to see it live.</p></div>
          <button className="btn btn-ghost" onClick={() => setShowPatient(!showPatient)}>{showPatient ? "Hide" : "Show"}</button></div>
        {showPatient && <div className="mt-4"><PatientPreviewPair /></div>}
      </div>
    </>
  );
}

"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHead, Skeleton, useFetch } from "@/components/ui";
import { useConfirm, useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";
import { ChannelsPanel } from "@/components/ChannelsPanel";

const TABS = ["Branding", "Departments", "Feedback questions", "Themes", "SLA and routing", "Feedback channels", "KPI definitions", "Notifications", "Privacy", "Maintenance"];

export default function Settings() {
  const me = useMe(); const toast = useToast(); const confirm = useConfirm();
  const [tab, setTab] = useState(TABS[0]);
  const edit = can(me, "settings", "admin");
  const save = (key: string, value: any) => api(`/settings/${key}`, { method: "PUT", body: { value } }).then(() => toast("Saved")).catch((e) => toast(e.message, "err"));
  return (
    <>
      <PageHead title="Settings" sub="Configure Antier Healthcare Suite for your hospital. Changes apply immediately." />
      {!edit && <p className="text-sm mb-3" style={{ color: "var(--muted)" }}>You have view-only access. Ask an Admin to make changes.</p>}
      <div className="flex gap-2 mb-4 flex-wrap">{TABS.map((t) => <button key={t} className={`btn ${tab === t ? "" : "btn-ghost"}`} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === "Branding" && <Branding edit={edit} />}
      {tab === "Departments" && <Departments edit={edit} />}
      {tab === "Feedback questions" && <Questions edit={edit} save={save} />}
      {tab === "Themes" && <Themes edit={edit} save={save} />}
      {tab === "SLA and routing" && <Sla edit={edit} save={save} />}
      {tab === "Feedback channels" && <ChannelsPanel edit={edit} />}
      {tab === "KPI definitions" && <>
        <div className="card p-4 mb-4 max-w-4xl text-sm">These three targets drive the patient-experience cards on the home page. The full set of quality indicators, with definitions, numerators, denominators and targets, is in the <Link className="underline" href="/quality/indicators">indicator dictionary</Link>{can(me, "indicators", "admin") ? ", where you can edit them and add new ones." : "."}</div>
        <Kpis edit={edit} save={save} /></>}
      {tab === "Notifications" && <Notif edit={edit} save={save} />}
      {tab === "Privacy" && <Privacy edit={edit} save={save} />}
      {tab === "Maintenance" && (
        <div className="card p-5 space-y-3 max-w-xl"><h2 className="font-medium">Reset sandbox data</h2>
          <p className="text-sm" style={{ color: "var(--muted)" }}>Restores the original sample data so the next walkthrough starts clean. All changes made since will be lost.</p>
          {edit ? <button className="btn btn-danger" onClick={async () => { if (await confirm({ title: "Reset sandbox data?", body: "This permanently replaces all current records with the sample data. You will be signed out.", label: "Reset", danger: true })) { toast("Resetting…"); await api("/admin/reset-sandbox", { body: {} }).then(() => { toast("Sandbox data restored"); setTimeout(() => { localStorage.removeItem("ahs_token"); location.href = "/login"; }, 1200); }).catch((e) => toast(e.message, "err")); } }}>Reset sandbox data</button> : <p className="text-sm">Admin only.</p>}</div>
      )}
    </>
  );
}

function Branding({ edit }: any) {
  const org = useFetch<any>("/organisation"); const toast = useToast();
  const [v, setV] = useState<any>(null);
  useEffect(() => { if (org.data) setV(org.data); }, [org.data]);
  if (!v) return <Skeleton rows={3} />;
  const b = v.branding;
  const setB = (k: string, x: string) => setV({ ...v, branding: { ...b, [k]: x } });
  return (
    <div className="card p-5 max-w-xl space-y-3">
      <div><label className="label">Hospital name</label><input className="input" disabled={!edit} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} /></div>
      <div><label className="label">Logo URL (shown on sign-in, header, patient form)</label><input className="input" disabled={!edit} value={b.logo_url || ""} placeholder="https://…/logo.png" onChange={(e) => setB("logo_url", e.target.value)} /></div>
      <div><label className="label">Primary colour</label><input type="color" disabled={!edit} value={b.primary_color || "#0f766e"} onChange={(e) => setB("primary_color", e.target.value)} /></div>
      <div><label className="label">Message sender name</label><input className="input" disabled={!edit} value={b.sender_name || ""} onChange={(e) => setB("sender_name", e.target.value)} /></div>
      {edit && <button className="btn" onClick={() => api("/organisation", { method: "PUT", body: v }).then(() => { document.documentElement.style.setProperty("--brand", b.primary_color); toast("Branding saved"); }).catch((e) => toast(e.message, "err"))}>Save branding</button>}
    </div>
  );
}

function Departments({ edit }: any) {
  const d = useFetch<any[]>("/departments"); const toast = useToast(); const [n, setN] = useState(""); const [ar, setAr] = useState("");
  if (d.loading) return <Skeleton />;
  const upd = (x: any) => api(`/departments/${x.id}`, { method: "PUT", body: x }).then(() => { toast("Saved"); d.reload(); });
  return (
    <div className="card p-4 max-w-2xl space-y-2">
      {d.data!.map((x) => <div key={x.id} className="flex gap-2 items-center"><input className="input" disabled={!edit} defaultValue={x.name} onBlur={(e) => e.target.value !== x.name && upd({ ...x, name: e.target.value })} />
        <input className="input" dir="rtl" disabled={!edit} defaultValue={x.name_ar} onBlur={(e) => e.target.value !== x.name_ar && upd({ ...x, name_ar: e.target.value })} />
        <label className="text-xs flex gap-1"><input type="checkbox" disabled={!edit} checked={x.active} onChange={(e) => upd({ ...x, active: e.target.checked })} />Active</label></div>)}
      {edit && <div className="flex gap-2 pt-2"><input className="input" placeholder="New department" value={n} onChange={(e) => setN(e.target.value)} /><input className="input" dir="rtl" placeholder="الاسم بالعربية" value={ar} onChange={(e) => setAr(e.target.value)} />
        <button className="btn" onClick={() => n.trim() ? api("/departments", { body: { name: n, name_ar: ar } }).then(() => { setN(""); setAr(""); toast("Department added"); d.reload(); }) : toast("Enter a name", "err")}>Add</button></div>}
    </div>
  );
}

function Questions({ edit, save }: any) {
  const s = useFetch<any>("/settings/questions"); const [q, setQ] = useState<any[] | null>(null);
  useEffect(() => { if (s.data) setQ(s.data.value); }, [s.data]);
  if (!q) return <Skeleton />;
  const up = (i: number, k: string, v: any) => setQ(q.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  return (
    <div className="card p-4 space-y-3 max-w-3xl">
      <p className="text-xs" style={{ color: "var(--muted)" }}>Patients see up to 5 active questions, in their language.</p>
      {q.map((x, i) => <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2 items-center"><input className="input" disabled={!edit} value={x.en} onChange={(e) => up(i, "en", e.target.value)} /><input dir="rtl" className="input" disabled={!edit} value={x.ar} onChange={(e) => up(i, "ar", e.target.value)} />
        <label className="text-xs flex gap-1"><input type="checkbox" disabled={!edit} checked={x.active} onChange={(e) => up(i, "active", e.target.checked)} />On</label></div>)}
      {edit && <div className="flex gap-2"><button className="btn btn-ghost" onClick={() => q.length < 8 ? setQ([...q, { key: "q" + (q.length + 1), en: "", ar: "", active: true }]) : null}>Add question</button>
        <button className="btn" onClick={() => q.some((x) => x.active && (!x.en.trim() || !x.ar.trim())) ? alert("Active questions need English and Arabic text.") : save("questions", q)}>Save questions</button></div>}
    </div>
  );
}

function Themes({ edit, save }: any) {
  const s = useFetch<any>("/settings/themes"); const [t, setT] = useState<string[] | null>(null); const [n, setN] = useState("");
  useEffect(() => { if (s.data) setT(s.data.value); }, [s.data]);
  if (!t) return <Skeleton />;
  return (
    <div className="card p-4 max-w-xl space-y-3"><p className="text-xs" style={{ color: "var(--muted)" }}>AI analysis picks themes from this list; it may propose new ones, flagged as new.</p>
      <div className="flex flex-wrap gap-2">{t.map((x) => <span key={x} className="px-2.5 py-1 rounded-full text-sm border flex gap-1.5" style={{ borderColor: "var(--line)" }}>{x}{edit && <button aria-label={`Remove ${x}`} onClick={() => setT(t.filter((y) => y !== x))}>×</button>}</span>)}</div>
      {edit && <div className="flex gap-2"><input className="input" placeholder="New theme" value={n} onChange={(e) => setN(e.target.value)} /><button className="btn btn-ghost" onClick={() => { if (n.trim() && !t.includes(n.trim())) { setT([...t, n.trim()]); setN(""); } }}>Add</button><button className="btn" onClick={() => save("themes", t)}>Save themes</button></div>}</div>
  );
}

function Sla({ edit, save }: any) {
  const sla = useFetch<any>("/settings/sla"); const rt = useFetch<any>("/settings/routing");
  const [a, setA] = useState<any>(null); const [r, setR] = useState<any>(null);
  useEffect(() => { if (sla.data) setA(sla.data.value); }, [sla.data]); useEffect(() => { if (rt.data) setR(rt.data.value); }, [rt.data]);
  if (!a || !r) return <Skeleton />;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl">
      <div className="card p-4 space-y-3"><h2 className="font-medium text-sm">Case SLA (hours)</h2>
        {["high", "medium", "low"].map((k) => <div key={k}><label className="label">{k} urgency</label><input type="number" min={1} className="input" disabled={!edit} value={a[k]} onChange={(e) => setA({ ...a, [k]: Number(e.target.value) })} /></div>)}
        {edit && <button className="btn" onClick={() => Object.values(a).some((v: any) => !(v > 0)) ? alert("SLA hours must be positive.") : save("sla", a)}>Save SLA</button>}</div>
      <div className="card p-4 space-y-3"><h2 className="font-medium text-sm">Routing rule</h2>
        <div><label className="label">Google invitation: minimum rating</label><input type="number" min={1} max={5} className="input" disabled={!edit} value={r.min_rating} onChange={(e) => setR({ ...r, min_rating: Number(e.target.value) })} /></div>
        <div><label className="label">Feedback request delay (hours)</label><input type="number" min={0} className="input" disabled={!edit} value={r.feedback_delay_hours} onChange={(e) => setR({ ...r, feedback_delay_hours: Number(e.target.value) })} /></div>
        <div><label className="label">Review link</label><input className="input" disabled={!edit} value={r.google_review_url} onChange={(e) => setR({ ...r, google_review_url: e.target.value })} /></div>
        <p className="text-xs" style={{ color: "var(--muted)" }}>Satisfied patients (rating at or above the minimum and positive sentiment) see the Google invitation. Everyone else sees a neutral thank-you and an internal case is opened. Nobody is blocked from posting a public review.</p>
        {edit && <button className="btn" onClick={() => save("routing", r)}>Save routing</button>}</div>
    </div>
  );
}

function Kpis({ edit, save }: any) {
  const s = useFetch<any>("/settings/kpis"); const [k, setK] = useState<any[] | null>(null);
  useEffect(() => { if (s.data) setK(s.data.value); }, [s.data]);
  if (!k) return <Skeleton />;
  const up = (i: number, f: string, v: any) => setK(k.map((x, j) => (j === i ? { ...x, [f]: v } : x)));
  return (
    <div className="card p-4 max-w-4xl"><table className="w-full"><thead><tr><th className="th">KPI</th><th className="th">Formula</th><th className="th">Direction</th><th className="th">Target (green)</th><th className="th">Amber limit</th></tr></thead>
      <tbody>{k.map((x, i) => <tr key={x.key}><td className="td">{x.name}</td><td className="td text-xs">{x.formula}</td><td className="td">{x.direction}</td>
        <td className="td"><input type="number" step="0.1" className="input !w-24" disabled={!edit} value={x.target} onChange={(e) => up(i, "target", Number(e.target.value))} /></td>
        <td className="td"><input type="number" step="0.1" className="input !w-24" disabled={!edit} value={x.amber} onChange={(e) => up(i, "amber", Number(e.target.value))} /></td></tr>)}</tbody></table>
      {edit && <button className="btn mt-3" onClick={() => save("kpis", k)}>Save KPI definitions</button>}</div>
  );
}

function Notif({ edit, save }: any) {
  const s = useFetch<any>("/settings/escalation"); const emails = useFetch<any[]>("/emails"); const roles = useFetch<any[]>("/roles");
  const [e, setE] = useState<any>(null); useEffect(() => { if (s.data) setE(s.data.value); }, [s.data]);
  if (!e) return <Skeleton />;
  return (
    <div className="space-y-4 max-w-3xl">
      <div className="card p-4 space-y-3"><h2 className="font-medium text-sm">Escalation rules</h2>
        {[["sla_breach", "SLA breach escalates to"], ["overdue_action", "Overdue corrective action escalates to"]].map(([k, l]) => <div key={k}><label className="label">{l}</label>
          <select className="input" disabled={!edit} value={e[k]} onChange={(ev) => setE({ ...e, [k]: ev.target.value })}>{roles.data?.filter((r) => (r.permissions.cases || []).includes("approve") || (r.permissions.incidents || []).includes("approve")).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></div>)}
        {edit && <button className="btn" onClick={() => save("escalation", e)}>Save rules</button>}</div>
      <div className="card p-4"><h2 className="font-medium text-sm mb-2">Recent outgoing email</h2>
        {!emails.data?.length ? <p className="text-sm" style={{ color: "var(--muted)" }}>No emails sent yet.</p> : emails.data.slice(0, 10).map((m) => <div key={m.id} className="td text-xs flex justify-between"><span>{m.subject} → {m.to}</span><span>{m.status}</span></div>)}</div>
    </div>
  );
}

function Privacy({ edit, save }: any) {
  const rt = useFetch<any>("/settings/routing"); const org = useFetch<any>("/organisation");
  const [r, setR] = useState<any>(null); useEffect(() => { if (rt.data) setR(rt.data.value); }, [rt.data]);
  if (!r) return <Skeleton />;
  return (
    <div className="card p-4 max-w-xl space-y-3">
      <label className="flex gap-2 text-sm items-center"><input type="checkbox" disabled={!edit} checked={r.mask_patient_names} onChange={(e) => setR({ ...r, mask_patient_names: e.target.checked })} /> Mask patient names in lists and cases</label>
      <p className="text-xs" style={{ color: "var(--muted)" }}>Deployment: {org.data?.profile?.deployment_note}</p>
      {edit && <button className="btn" onClick={() => save("routing", r)}>Save privacy settings</button>}</div>
  );
}

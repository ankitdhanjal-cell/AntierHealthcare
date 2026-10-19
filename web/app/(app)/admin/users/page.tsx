"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Badge, ErrorBox, PageHead, Skeleton, useFetch } from "@/components/ui";
import { useConfirm, useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

const MODULES = ["feedback", "cases", "dashboard", "incidents", "accreditation", "audits", "indicators", "reports", "audit", "integrations", "settings", "users"];
const MOD_LABEL: Record<string, string> = { audit: "audit trail", audits: "clinical audits", dashboard: "overview" };

export default function Users() {
  const me = useMe(); const toast = useToast(); const confirm = useConfirm();
  const users = useFetch<any[]>("/users"); const roles = useFetch<any[]>("/roles"); const depts = useFetch<any[]>("/departments");
  const [editing, setEditing] = useState(""); const [tab, setTab] = useState("users"); const [form, setForm] = useState<any>(null); const [err, setErr] = useState(""); const [link, setLink] = useState("");
  const admin = can(me, "users", "admin");
  async function invite() {
    setErr("");
    if (!form.name || !form.email.includes("@") || !form.role) return setErr("Name, a valid email and a role are required.");
    try { const r = await api("/users", { body: form }); setLink(r.invite_link); toast("Invitation sent"); users.reload(); setForm(null); } catch (e: any) { setErr(e.message); }
  }
  const patch = (id: string, body: any, msg: string) => api(`/users/${id}`, { method: "PUT", body }).then(() => { toast(msg); users.reload(); }).catch((e) => toast(e.message, "err"));
  const dname = (ids: string[]) => ids.length ? ids.map((i) => depts.data?.find((d) => d.id === i)?.name).filter(Boolean).join(", ") : "All departments";
  return (
    <>
      <PageHead title="Users and roles" sub="Invite staff, assign roles and departments">
        {can(me, "users", "create") && <button className="btn" onClick={() => { setForm({ name: "", email: "", role: "", department_ids: [] }); setLink(""); }}>Invite user</button>}
      </PageHead>
      <div className="flex gap-2 mb-3">{["users", "matrix"].map((t) => <button key={t} className={`btn ${tab === t ? "" : "btn-ghost"}`} onClick={() => setTab(t)}>{t === "users" ? "Users" : "Permission matrix"}</button>)}</div>
      {link && <div className="card p-3 mb-3 text-xs break-all">Invitation link (also emailed): {link}</div>}
      {form && <div className="card p-4 mb-4 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <div><label className="label">Name</label><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div><label className="label">Email</label><input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <div><label className="label">Role</label><select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option value="">Choose…</option>{roles.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></div>
        <div><label className="label">Departments</label><select multiple className="input" value={form.department_ids} onChange={(e) => setForm({ ...form, department_ids: Array.from(e.target.selectedOptions).map((o) => o.value) })}>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
        {err && <p className="text-sm text-red-600 md:col-span-4">{err}</p>}
        <div className="flex gap-2"><button className="btn" onClick={invite}>Send invitation</button><button className="btn btn-ghost" onClick={() => setForm(null)}>Cancel</button></div></div>}
      {users.loading || roles.loading ? <Skeleton /> : users.error ? <ErrorBox msg={users.error} retry={users.reload} /> : tab === "users" ? (
        <div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Name</th><th className="th">Email</th><th className="th">Role</th><th className="th">Departments</th><th className="th">Status</th><th className="th"></th></tr></thead>
          <tbody>{users.data!.map((u) => <tr key={u.id}><td className="td">{u.name}</td><td className="td">{u.email}</td>
            <td className="td">{admin && editing === u.id ? <select className="input !w-48" autoFocus value={u.role} onBlur={() => setEditing("")} onChange={(e) => { patch(u.id, { role: e.target.value }, "Role updated"); setEditing(""); }}>{roles.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select> : <span>{u.role_name}{admin && u.id !== me.id && <button className="ms-2 text-xs underline" onClick={() => setEditing(u.id)}>Change role</button>}</span>}</td>
            <td className="td text-xs">{dname(u.department_ids)}</td><td className="td"><Badge k={u.active ? "green" : "neutral"}>{u.invited && u.active ? "Invited" : u.active ? "Active" : "Inactive"}</Badge></td>
            <td className="td">{admin && u.id !== me.id && <button className="text-xs underline" onClick={async () => { if (!u.active || await confirm({ title: `Deactivate ${u.name}?`, body: "They will no longer be able to sign in.", label: "Deactivate", danger: true })) patch(u.id, { active: !u.active }, u.active ? "User deactivated" : "User reactivated"); }}>{u.active ? "Deactivate" : "Reactivate"}</button>}</td></tr>)}</tbody></table></div>
      ) : (
        <div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Role</th><th className="th">Scope</th>{MODULES.map((m) => <th key={m} className="th capitalize">{MOD_LABEL[m] || m}</th>)}</tr></thead>
          <tbody>{roles.data!.map((r) => <tr key={r.id}><td className="td font-medium">{r.name}</td><td className="td text-xs">{r.sees_all ? "All records" : "Own departments"}</td>
            {MODULES.map((m) => <td key={m} className="td text-xs">{(r.permissions[m] || []).join(", ") || "—"}</td>)}</tr>)}</tbody></table></div>
      )}
    </>
  );
}

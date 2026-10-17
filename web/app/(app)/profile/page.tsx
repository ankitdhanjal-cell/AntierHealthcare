"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { PageHead } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { useMe } from "@/components/Shell";

export default function Profile() {
  const me = useMe(); const toast = useToast();
  const [name, setName] = useState(me.name); const [cur, setCur] = useState(""); const [nw, setNw] = useState(""); const [err, setErr] = useState("");
  return (
    <>
      <PageHead title="Profile" sub={`${me.email} · ${me.role_name}`} />
      <div className="grid md:grid-cols-2 gap-4 max-w-3xl">
        <div className="card p-4 space-y-3"><div><label className="label">Name</label><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></div>
          <button className="btn" onClick={() => name.trim() ? api("/auth/profile", { method: "PUT", body: { name } }).then(() => toast("Profile saved")) : toast("Name is required", "err")}>Save</button></div>
        <div className="card p-4 space-y-3"><div><label className="label">Current password</label><input type="password" className="input" value={cur} onChange={(e) => setCur(e.target.value)} /></div>
          <div><label className="label">New password (min 8 characters)</label><input type="password" className="input" value={nw} onChange={(e) => setNw(e.target.value)} /></div>
          {err && <p className="text-sm text-red-600">{err}</p>}
          <button className="btn" onClick={() => api("/auth/change-password", { body: { current: cur, new: nw } }).then(() => { toast("Password changed"); setCur(""); setNw(""); setErr(""); }).catch((e) => setErr(e.message))}>Change password</button></div>
      </div>
    </>
  );
}

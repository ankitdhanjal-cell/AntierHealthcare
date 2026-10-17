"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, setToken } from "@/lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [b, setB] = useState<any>({});
  const router = useRouter();
  useEffect(() => { api("/auth/branding", { auth: false }).then(setB).catch(() => {}); }, []);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.includes("@")) return setErr("Enter a valid email address.");
    if (!password) return setErr("Enter your password.");
    setBusy(true); setErr("");
    try { const r = await api("/auth/login", { body: { email, password }, auth: false }); setToken(r.token); router.replace("/"); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form onSubmit={submit} className="card p-7 w-full max-w-sm space-y-4" noValidate>
        <div className="text-center">
          <div className="mx-auto w-11 h-11 rounded-xl flex items-center justify-center text-white text-xl font-bold" style={{ background: "var(--brand)" }}>+</div>
          <h1 className="text-lg font-semibold mt-3">Antier Healthcare Suite</h1>
          <p className="text-sm" style={{ color: "var(--muted)" }}>Sign in to {b.hospital || "your hospital"}</p>
        </div>
        <div><label className="label" htmlFor="e">Email</label><input id="e" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus /></div>
        <div><label className="label" htmlFor="p">Password</label><input id="p" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        {err && <p className="text-sm text-red-600" role="alert">{err}</p>}
        <button className="btn w-full justify-center" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <div className="flex justify-between text-xs" style={{ color: "var(--muted)" }}>
          <Link href="/forgot">Forgot password?</Link><span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-semibold">Sandbox</span>
        </div>
        <details className="text-xs" style={{ color: "var(--muted)" }}>
          <summary className="cursor-pointer">Sandbox logins</summary>
          <p className="mt-1">Password for all users: Sandbox@2026</p>
          <ul className="mt-1 space-y-0.5">{["quality.manager", "patient.relations", "dept.head", "infection.control", "staff", "front.desk", "management", "admin"].map((u) => <li key={u}><button type="button" className="underline" onClick={() => { setEmail(`${u}@hospital.example`); setPassword("Sandbox@2026"); }}>{u}@hospital.example</button></li>)}</ul>
        </details>
      </form>
    </div>
  );
}

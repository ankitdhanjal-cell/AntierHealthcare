"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, rememberMe, setToken } from "@/lib/api";

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
    try { const r = await api("/auth/login", { body: { email, password }, auth: false }); setToken(r.token); rememberMe(r.user); router.replace("/"); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div className="min-h-screen grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="hidden lg:flex flex-col justify-between p-12 text-white" style={{ background: "var(--side)" }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded flex items-center justify-center" style={{ background: "var(--brand)" }}><svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true"><path d="M6.5 1h3v5.5H15v3H9.5V15h-3V9.5H1v-3h5.5z" fill="currentColor" /></svg></div>
          <div className="leading-tight"><div className="font-semibold">{b.hospital || "Antier Healthcare Suite"}</div><div className="text-xs" style={{ color: "var(--side-muted)" }}>Healthcare Suite</div></div>
        </div>
        <div className="max-w-md">
          <h2 className="text-[28px] leading-9 font-semibold">What patients tell you, and what you do about it, in one place.</h2>
          <p className="mt-4 text-[15px]" style={{ color: "var(--side-ink)" }}>Feedback and complaints, incident reporting, audits, accreditation evidence and the monthly committee pack.</p>
        </div>
        <p className="text-xs" style={{ color: "var(--side-muted)" }}>Version {b.version}</p>
      </aside>
      <main className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-4" noValidate>
          <div>
            <h1 className="text-2xl font-semibold">Sign in</h1>
            <p className="text-[13px] mt-1" style={{ color: "var(--muted)" }}>{b.hospital ? `to ${b.hospital}` : "to your account"}</p>
          </div>
          <div><label className="label" htmlFor="e">Email</label><input id="e" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus autoComplete="username" /></div>
          <div><label className="label" htmlFor="p">Password</label><input id="p" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></div>
          {err && <p className="text-[13px]" style={{ color: "var(--bad)" }} role="alert">{err}</p>}
          <button className="btn w-full" style={{ minHeight: 38 }} disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          <div className="text-xs"><Link href="/forgot" className="underline" style={{ color: "var(--muted)" }}>Forgot your password?</Link></div>
          <details className="text-xs pt-3" style={{ color: "var(--muted)", borderTop: "1px solid var(--line)" }}>
            <summary className="cursor-pointer py-1">Test accounts</summary>
            <p className="mt-1">The password for every account is Sandbox@2026.</p>
            <ul className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5">{["quality.manager", "patient.relations", "dept.head", "nurse.manager", "infection.control", "staff", "front.desk", "management", "admin"].map((u) => <li key={u}><button type="button" className="underline" onClick={() => setEmail(`${u}@hospital.example`)}>{u}</button></li>)}</ul>
          </details>
        </form>
      </main>
    </div>
  );
}

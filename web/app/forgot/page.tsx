"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
export default function Forgot() {
  const [email, setEmail] = useState(""); const [done, setDone] = useState(false);
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form className="card p-7 w-full max-w-sm space-y-4" onSubmit={async (e) => { e.preventDefault(); await api("/auth/forgot", { body: { email }, auth: false }).catch(() => {}); setDone(true); }}>
        <h1 className="text-lg font-semibold">Reset your password</h1>
        {done ? <p className="text-sm">If that account exists, a reset link has been emailed.</p> : <>
          <div><label className="label" htmlFor="e">Email</label><input id="e" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <button className="btn w-full justify-center">Send reset link</button></>}
        <Link href="/login" className="text-xs underline">Back to sign in</Link>
      </form>
    </div>
  );
}

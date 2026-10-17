"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api } from "@/lib/api";
function Form() {
  const token = useSearchParams().get("token") || ""; const router = useRouter();
  const [pw, setPw] = useState(""); const [err, setErr] = useState("");
  return (
    <form className="card p-7 w-full max-w-sm space-y-4" onSubmit={async (e) => { e.preventDefault(); if (pw.length < 8) return setErr("Password must be at least 8 characters.");
      try { await api("/auth/reset", { body: { token, password: pw }, auth: false }); router.replace("/login"); } catch (e: any) { setErr(e.message); } }}>
      <h1 className="text-lg font-semibold">Set a new password</h1>
      <div><label className="label" htmlFor="p">New password</label><input id="p" type="password" className="input" value={pw} onChange={(e) => setPw(e.target.value)} /></div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <button className="btn w-full justify-center">Save password</button>
    </form>
  );
}
export default function Reset() { return <div className="min-h-screen flex items-center justify-center p-4"><Suspense><Form /></Suspense></div>; }

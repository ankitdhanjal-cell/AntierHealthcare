"use client";
import Link from "next/link";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="card p-10 max-w-xl mx-auto mt-8 text-center">
      <p className="text-xs uppercase tracking-wider" style={{ color: "var(--muted)" }}>Something went wrong</p>
      <h1 className="text-xl font-semibold mt-2">This page could not be shown</h1>
      <p className="text-sm mt-2 mb-5" style={{ color: "var(--muted)" }}>Try again. If it keeps happening, go back to Home and tell your administrator which page you were on.</p>
      <div className="flex gap-2 justify-center"><button className="btn" onClick={reset}>Try again</button><Link href="/" className="btn btn-ghost">Back to Home</Link></div>
    </div>
  );
}

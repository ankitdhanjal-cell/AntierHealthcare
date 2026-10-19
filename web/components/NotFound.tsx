"use client";
import Link from "next/link";

export function NotFoundPanel() {
  return (
    <div className="card p-10 max-w-xl mx-auto mt-8 text-center">
      <p className="text-xs uppercase tracking-wider" style={{ color: "var(--muted)" }}>Page not found</p>
      <h1 className="text-xl font-semibold mt-2">We could not find that page</h1>
      <p className="text-sm mt-2 mb-5" style={{ color: "var(--muted)" }}>The link may be out of date, or the record may have been removed. Use the menu or go back to the overview.</p>
      <Link href="/" className="btn">Back to Home</Link>
    </div>
  );
}

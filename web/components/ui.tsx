"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

export function useFetch<T = any>(path: string | null, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    if (!path) return;
    setLoading(true);
    api<T>(path).then((d) => { setData(d); setError(""); }).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [path]);
  useEffect(load, [load, ...deps]);
  return { data, loading, error, reload: load, setData };
}

export function Skeleton({ rows = 5 }: { rows?: number }) {
  return <div className="space-y-2 p-4">{Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton h-8" />)}</div>;
}

export function Empty({ title, hint, action }: { title: string; hint: string; action?: React.ReactNode }) {
  return (
    <div className="text-center py-14 px-4">
      <div className="mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-3" style={{ background: "var(--line)" }}>∅</div>
      <p className="font-medium">{title}</p>
      <p className="text-sm mt-1 mb-3" style={{ color: "var(--muted)" }}>{hint}</p>
      {action}
    </div>
  );
}

export function ErrorBox({ msg, retry }: { msg: string; retry?: () => void }) {
  return (
    <div className="card p-6 text-center">
      <p className="text-sm text-red-600 mb-2">{msg}</p>
      {retry && <button className="btn btn-ghost" onClick={retry}>Try again</button>}
    </div>
  );
}

const COLORS: Record<string, string> = {
  positive: "bg-emerald-100 text-emerald-800", neutral: "bg-slate-200 text-slate-800", negative: "bg-red-100 text-red-800",
  high: "bg-red-100 text-red-800", medium: "bg-amber-100 text-amber-800", low: "bg-slate-200 text-slate-800",
  New: "bg-sky-100 text-sky-800", Assigned: "bg-indigo-100 text-indigo-800", "In investigation": "bg-amber-100 text-amber-800",
  Resolved: "bg-emerald-100 text-emerald-800", Closed: "bg-slate-200 text-slate-700", Overdue: "bg-red-600 text-white",
  Sandbox: "bg-amber-100 text-amber-800", Available: "bg-slate-200 text-slate-800", ai: "bg-violet-100 text-violet-800",
  green: "bg-emerald-100 text-emerald-800", amber: "bg-amber-100 text-amber-800", red: "bg-red-100 text-red-800", new: "bg-sky-100 text-sky-800",
};
export const Badge = ({ k, children }: { k: string; children?: React.ReactNode }) => (
  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${COLORS[k] || COLORS.neutral}`}>{children ?? k}</span>
);
export const AiTag = () => <span className="ms-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-800 align-middle">AI suggested</span>;

export function Pager({ page, size, total, onPage }: { page: number; size: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <div className="flex items-center justify-between px-4 py-3 text-sm" style={{ borderTop: "1px solid var(--line)" }}>
      <span style={{ color: "var(--muted)" }}>{total} results</span>
      <div className="flex gap-2 items-center">
        <button className="btn btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <span>Page {page} of {pages}</span>
        <button className="btn btn-ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}

export const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—");
export const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleDateString([], { dateStyle: "medium" }) : "—");

export function PageHead({ title, sub, children }: { title: string; sub?: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-5 gap-3 flex-wrap">
      <div><h1 className="text-xl font-semibold">{title}</h1>{sub && <p className="text-sm mt-0.5" style={{ color: "var(--muted)" }}>{sub}</p>}</div>
      <div className="flex gap-2">{children}</div>
    </div>
  );
}

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
  near_miss: "bg-sky-100 text-sky-800", no_harm: "bg-slate-200 text-slate-800", mild: "bg-amber-100 text-amber-800", moderate: "bg-orange-200 text-orange-900",
  severe: "bg-red-600 text-white", death: "bg-red-800 text-white", Reported: "bg-sky-100 text-sky-800", Triaged: "bg-indigo-100 text-indigo-800",
  "Under investigation": "bg-amber-100 text-amber-800", "Actions open": "bg-violet-100 text-violet-800", Sentinel: "bg-red-600 text-white",
  Met: "bg-emerald-100 text-emerald-800", "Partially met": "bg-amber-100 text-amber-800", "Not met": "bg-red-100 text-red-800", "Not applicable": "bg-slate-200 text-slate-700",
  Scheduled: "bg-sky-100 text-sky-800",
  Completed: "bg-emerald-100 text-emerald-800", Open: "bg-slate-200 text-slate-800", "In progress": "bg-amber-100 text-amber-800",
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

let hospitalTz = "Asia/Muscat";
export const setHospitalTz = (tz?: string) => { if (tz) hospitalTz = tz; };

/** 17 Oct 2026 14:05 (24 h, hospital timezone) */
export const fmt = (d?: string | null) => {
  if (!d) return "—";
  return new Date(d).toLocaleString("en-GB", { timeZone: hospitalTz, day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).replace(",", "").replace("Sept", "Sep");
};
/** 17 Oct 2026 */
export const fmtDate = (d?: string | null) =>
  d ? new Date(d).toLocaleDateString("en-GB", { timeZone: hospitalTz, day: "2-digit", month: "short", year: "numeric" }).replace("Sept", "Sep") : "—";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** "2026-04" -> "Apr 2026" (short: "Apr") */
export const fmtMonth = (ym: string, short = false) => {
  const [y, m] = String(ym).split("-");
  const name = MONTHS[Number(m) - 1];
  return name ? (short ? name : `${name} ${y}`) : String(ym);
};
/** "2026-07" -> { date_from: "2026-07-01", date_to: "2026-07-31" } */
export const monthRange = (ym: string) => {
  const [y, m] = ym.split("-").map(Number);
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  return { date_from: `${ym}-01`, date_to: `${ym}-${String(last).padStart(2, "0")}` };
};
/** Hours -> "35 min", "36 h", "2.5 days" (one decimal at most) */
export const fmtDuration = (hours?: number | null) => {
  if (hours == null) return "—";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 48) return `${Number(hours.toFixed(1))} h`;
  return `${Number((hours / 24).toFixed(1))} days`;
};

/** Tiny trend line for tables. */
export function Spark({ values, color = "var(--brand)" }: { values: number[]; color?: string }) {
  if (values.length < 2) return <span style={{ color: "var(--muted)" }}>—</span>;
  const w = 90, h = 24, min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - 3 - ((v - min) / span) * (h - 6)}`).join(" ");
  const last = pts.split(" ").pop()!.split(",");
  return <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Trend"><polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" /><circle cx={last[0]} cy={last[1]} r="2.5" fill={color} /></svg>;
}

export const dayEndIso = (v: string) => new Date(v + "T23:59").toISOString();
export const dateInputValue = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString("en-CA") : "");
export const inDays = (n: number) => new Date(Date.now() + n * 86400000).toLocaleDateString("en-CA");

/** Horizontal bar for a percentage, with an optional target tick. */
export function PctBar({ pct, target, color = "var(--brand)" }: { pct: number; target?: number; color?: string }) {
  return (
    <div className="relative h-2.5 rounded-full overflow-hidden" style={{ background: "var(--line)" }} role="img" aria-label={`${pct}%`}>
      <div className="h-full rounded-full" style={{ width: `${Math.min(100, pct)}%`, background: color }} />
      {target != null && <div className="absolute top-0 h-full w-0.5" style={{ left: `${target}%`, background: "var(--ink)" }} title={`Target ${target}%`} />}
    </div>
  );
}

export function FilterChips({ items, onClear }: { items: [string, string][]; onClear: () => void }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 mb-3 text-xs">
      <span style={{ color: "var(--muted)" }}>Filtered by</span>
      {items.map(([k, v]) => <span key={k} className="px-2 py-0.5 rounded-full" style={{ background: "var(--line)" }}>{k}: {v}</span>)}
      <button className="underline" onClick={onClear}>Clear filters</button>
    </div>
  );
}

export function PageHead({ title, sub, children }: { title: string; sub?: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-5 gap-3 flex-wrap">
      <div><h1 className="text-xl font-semibold">{title}</h1>{sub && <p className="text-sm mt-0.5" style={{ color: "var(--muted)" }}>{sub}</p>}</div>
      <div className="flex gap-2 items-center flex-wrap">{children}</div>
    </div>
  );
}

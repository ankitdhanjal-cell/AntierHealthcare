"use client";
import { useCallback, useEffect, useState } from "react";
import { api, responseCache } from "@/lib/api";

/** Shown instead of a technical message when the server refuses a page (403). */
export const NO_ACCESS = "You do not have access to this page.";

export function useFetch<T = any>(path: string | null, deps: any[] = []) {
  const cached = path ? (responseCache.get(path) as T | undefined) : undefined;
  const [data, setData] = useState<T | null>(cached ?? null);
  const [loading, setLoading] = useState(!!path && cached === undefined);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    if (!path) { setLoading(false); return; }  // nothing to load (for example, this role may not call it)
    const hit = responseCache.get(path);
    if (hit !== undefined) { setData(hit); setLoading(false); } else setLoading(true);  // stale data now, fresh data a moment later
    api<T>(path).then((d) => {
      if (responseCache.size > 150) responseCache.delete(responseCache.keys().next().value as string);
      responseCache.set(path, d); setData(d); setError("");
    }).catch((e) => setError(e.status === 403 ? NO_ACCESS : e.message)).finally(() => setLoading(false));
  }, [path]);
  useEffect(load, [load, ...deps]);
  return { data, loading, error, reload: load, setData };
}

export function Skeleton({ rows = 5 }: { rows?: number }) {
  return <div className="space-y-2 p-4">{Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton h-8" />)}</div>;
}

export function Empty({ title, hint, action }: { title: string; hint: string; action?: React.ReactNode }) {
  return (
    <div className="py-12 px-6 max-w-md mx-auto text-center">
      <p className="font-medium">{title}</p>
      <p className="text-[13px] mt-1 mb-4" style={{ color: "var(--muted)" }}>{hint}</p>
      {action}
    </div>
  );
}

export function ErrorBox({ msg, retry }: { msg: string; retry?: () => void }) {
  if (msg === NO_ACCESS) {
    return (
      <div className="card p-8 text-center max-w-xl mx-auto mt-4">
        <p className="text-xs uppercase tracking-wider" style={{ color: "var(--muted)" }}>No access</p>
        <h1 className="text-lg font-semibold mt-1">This page is not available for your role</h1>
        <p className="text-sm mt-2 mb-4" style={{ color: "var(--muted)" }}>Your account does not include this area. If you need it, ask an administrator to change your role.</p>
        <a href="/" className="btn">Back to Home</a>
      </div>
    );
  }
  return (
    <div className="card p-6 text-center">
      <p className="text-sm text-red-600 mb-2">{msg}</p>
      {retry && <button className="btn btn-ghost" onClick={retry}>Try again</button>}
    </div>
  );
}

const TONE: Record<string, string> = {
  positive: "ok", negative: "bad", neutral: "", high: "bad", medium: "warn", low: "",
  New: "info", Assigned: "info", "In investigation": "warn", Resolved: "ok", Closed: "", Overdue: "solid",
  Sandbox: "warn", Available: "", ai: "vio",
  near_miss: "info", no_harm: "", mild: "warn", moderate: "warn", severe: "solid", death: "solid",
  Reported: "info", Triaged: "info", "Under investigation": "warn", "Actions open": "vio", Sentinel: "solid",
  Met: "ok", "Partially met": "warn", "Not met": "bad", "Not applicable": "",
  Scheduled: "info", Completed: "ok", Open: "", "In progress": "warn",
  green: "ok", amber: "warn", red: "bad", new: "info",
};
export const Badge = ({ k, children }: { k: string; children?: React.ReactNode }) => (
  <span className={`bdg ${TONE[k] ? `bdg-${TONE[k]}` : ""} capitalize`}>{children ?? String(k).replace(/_/g, " ")}</span>
);
export const AiTag = () => <span className="bdg bdg-vio ms-1.5" style={{ fontSize: 10.5 }} title="Suggested by the AI; staff confirm or change it">AI suggestion</span>;

export function Pager({ page, size, total, onPage }: { page: number; size: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <div className="flex items-center justify-between px-4 py-3 text-sm" style={{ borderTop: "1px solid var(--line)" }}>
      <span style={{ color: "var(--muted)" }}>{total} {total === 1 ? "result" : "results"}</span>
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
/** Hours -> "35 min", "18 h", "2.5 days" (one decimal at most) */
export const fmtDuration = (hours?: number | null) => {
  if (hours == null) return "—";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 24) return `${Number(hours.toFixed(1))} h`;
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
    <div className="relative h-2 rounded-sm overflow-hidden" style={{ background: "var(--line)" }} role="img" aria-label={`${pct}%`}>
      <div className="h-full" style={{ width: `${Math.min(100, pct)}%`, background: color }} />
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
    <div className="flex items-end justify-between mb-5 pb-4 gap-3 flex-wrap" style={{ borderBottom: "1px solid var(--line)" }}>
      <div className="min-w-0"><h1 className="text-[22px] leading-7 font-semibold">{title}</h1>{sub && <p className="text-[13px] mt-1 max-w-3xl" style={{ color: "var(--muted)" }}>{sub}</p>}</div>
      <div className="flex gap-2 items-center flex-wrap">{children}</div>
    </div>
  );
}

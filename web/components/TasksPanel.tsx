"use client";
import Link from "next/link";
import { Badge, ErrorBox, Skeleton, fmtDate, useFetch } from "./ui";

/** Cases, incidents, actions, audits and evidence reviews assigned to me, soonest first. */
export function TasksPanel() {
  const { data, loading, error, reload } = useFetch<any>("/tasks");
  return (
    <div className="card">
      <div className="p-4 flex justify-between items-baseline"><h2 className="font-medium text-sm">My tasks</h2>{data && <span className="text-xs" style={{ color: data.overdue ? "#dc2626" : "var(--muted)" }}>{data.total} open{data.overdue ? ` · ${data.overdue} overdue` : ""}</span>}</div>
      {loading ? <Skeleton rows={3} /> : error || !data ? <ErrorBox msg={error} retry={reload} /> : data.items.length === 0 ? <p className="px-4 pb-4 text-sm" style={{ color: "var(--muted)" }}>Nothing is assigned to you right now.</p> : (
        <ul className="max-h-[26rem] overflow-auto">{data.items.map((t: any, n: number) => (
          <li key={n} style={{ borderTop: "1px solid var(--line)" }}>
            <Link href={t.href} className="flex items-start justify-between gap-3 px-4 py-2.5 hover:bg-black/5">
              <span className="min-w-0 text-sm"><span className="block truncate">{t.title}</span><span className="text-xs" style={{ color: "var(--muted)" }}>{t.kind}{t.detail ? ` · ${t.detail}` : ""}</span></span>
              <span className="text-xs whitespace-nowrap text-end">{t.due_at ? <>{t.overdue && <Badge k="Overdue" />}<span className="block" style={{ color: t.overdue ? "#dc2626" : "var(--muted)" }}>{fmtDate(t.due_at)}</span></> : ""}</span>
            </Link></li>))}</ul>)}
    </div>
  );
}

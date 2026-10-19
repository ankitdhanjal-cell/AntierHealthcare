"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, fetchAllPages, qs } from "@/lib/api";
import { ExportBar } from "@/components/ExportBar";
import { Badge, Empty, ErrorBox, FilterChips, PageHead, Pager, Skeleton, fmt, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";

const FILTERS = ["q", "department_id", "rating", "sentiment", "theme", "language", "not_positive", "has_comment", "date_from", "date_to"];
const LABELS: Record<string, string> = { q: "Search", department_id: "Department", rating: "Rating", sentiment: "Sentiment", theme: "Theme", language: "Language", not_positive: "Sentiment", has_comment: "Comment", date_from: "From", date_to: "To" };

function Inbox() {
  const sp = useSearchParams();
  // Opened directly, the inbox shows responses with a comment first (most ratings come with no text). Arriving from a dashboard number keeps that number's own filter.
  const fromLink = FILTERS.some((k) => sp.get(k));
  const initial = () => ({ page: 1, size: 15, sort: "created_at", order: "desc", ...(fromLink ? {} : { has_comment: "true" }), ...Object.fromEntries(FILTERS.filter((k) => sp.get(k)).map((k) => [k, sp.get(k)])) });
  const [f, setF] = useState<any>(initial);
  const [sel, setSel] = useState<string[]>([]);
  const toast = useToast();
  const depts = useFetch<any[]>("/departments");
  const themes = useFetch<any>("/settings/themes");
  const { data, loading, error, reload } = useFetch<any>("/feedback" + qs(f), [JSON.stringify(f)]);
  const set = (k: string, v: any) => setF({ ...f, [k]: v, page: 1 });
  const sort = (k: string) => setF({ ...f, sort: k, order: f.sort === k && f.order === "desc" ? "asc" : "desc" });
  const active = FILTERS.filter((k) => f[k]).map((k): [string, string] => [LABELS[k], k === "not_positive" ? "neutral or negative" : k === "has_comment" ? "only with a comment" : String(f[k])]);
  const Th = ({ k, children }: any) => <th className="th cursor-pointer select-none" onClick={() => sort(k)}>{children}{f.sort === k ? (f.order === "desc" ? " ↓" : " ↑") : ""}</th>;
  return (
    <>
      <PageHead title="Feedback inbox" sub="Post-discharge responses, newest first">
        <ExportBar filename="feedback" fetchAll={() => fetchAllPages("/feedback", f)} columns={[["Received", (r) => fmt(r.created_at)], ["Patient", (r) => r.patient], ["MRN", (r) => r.mrn], ["Department", (r) => r.department], ["Rating", (r) => r.rating],
          ["Recommend (0-10)", (r) => r.nps ?? ""], ["Sentiment", (r) => r.sentiment], ["Themes", (r) => r.themes.join("; ")], ["Urgency", (r) => r.urgency], ["Language", (r) => r.language], ["Summary", (r) => r.summary]]} />
        {sel.length > 0 && <button className="btn btn-ghost" onClick={async () => { await api("/feedback/bulk-review", { body: { ids: sel } }); toast(`${sel.length} marked reviewed`); setSel([]); reload(); }}>Mark {sel.length} reviewed</button>}
      </PageHead>
      <FilterChips items={active} onClear={() => { setF({ page: 1, size: 15, sort: "created_at", order: "desc" }); }} />
      <label className="flex items-center gap-2 text-[13px] mb-3"><input type="checkbox" checked={!!f.has_comment} onChange={(e) => set("has_comment", e.target.checked ? "true" : "")} /> Show only responses with a written comment <span style={{ color: "var(--muted)" }}>(untick to include ratings with no comment)</span></label>
      <div className="card p-3 mb-4 grid grid-cols-2 md:grid-cols-6 gap-2">
        <input className="input" placeholder="Search text…" value={f.q || ""} onChange={(e) => set("q", e.target.value)} aria-label="Search" />
        <select className="input" value={f.department_id || ""} onChange={(e) => set("department_id", e.target.value)} aria-label="Department"><option value="">All departments</option>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
        <select className="input" value={f.rating || ""} onChange={(e) => set("rating", e.target.value)} aria-label="Rating"><option value="">Any rating</option>{[5, 4, 3, 2, 1].map((r) => <option key={r}>{r}</option>)}</select>
        <select className="input" value={f.sentiment || ""} onChange={(e) => set("sentiment", e.target.value)} aria-label="Sentiment"><option value="">Any sentiment</option><option>positive</option><option>neutral</option><option>negative</option></select>
        <select className="input" value={f.theme || ""} onChange={(e) => set("theme", e.target.value)} aria-label="Theme"><option value="">Any theme</option>{themes.data?.value.map((t: string) => <option key={t}>{t}</option>)}</select>
        <select className="input" value={f.language || ""} onChange={(e) => set("language", e.target.value)} aria-label="Language"><option value="">Any language</option><option value="en">English</option><option value="ar">Arabic</option></select>
      </div>
      <div className="card overflow-x-auto">
        {loading ? <Skeleton /> : error ? <ErrorBox msg={error} retry={reload} /> : data.items.length === 0 ? <Empty title="No feedback matches these filters" hint="Clear a filter, or send a discharge event from Admin → Integrations to collect a new response." /> : (
          <table className="w-full"><thead><tr><th className="th w-8"></th><Th k="created_at">Received</Th><th className="th">Patient</th><th className="th">Dept</th><Th k="rating">Rating</Th><th className="th">NPS</th><Th k="sentiment">Sentiment</Th><th className="th">Themes</th><Th k="urgency">Urgency</Th><th className="th">Summary</th></tr></thead>
            <tbody>{data.items.map((r: any) => (
              <tr key={r.id} className="hover:bg-black/5">
                <td className="td"><input type="checkbox" aria-label="Select" checked={sel.includes(r.id)} onChange={(e) => setSel(e.target.checked ? [...sel, r.id] : sel.filter((x) => x !== r.id))} /></td>
                <td className="td whitespace-nowrap">{fmt(r.created_at)}</td>
                <td className="td"><Link className="underline" href={`/feedback/${r.id}`}>{r.patient}</Link>{r.language === "ar" && <span className="ms-1 text-xs">AR</span>}{r.mrn && <span className="block text-xs" style={{ color: "var(--muted)" }}>{r.mrn}</span>}</td>
                <td className="td">{r.department}</td>
                <td className="td">{"★".repeat(r.rating)}<span style={{ opacity: 0.25 }}>{"★".repeat(5 - r.rating)}</span></td>
                <td className="td tabular-nums">{r.nps ?? "—"}</td>
                <td className="td">{r.ai_status === "needs_review" ? <Badge k="amber">Needs review</Badge> : <Badge k={r.sentiment} />}</td>
                <td className="td">{r.themes.map((t: string) => <span key={t} className="me-1 px-1.5 py-0.5 rounded text-xs" style={{ background: "var(--line)" }}>{t}</span>)}</td>
                <td className="td"><Badge k={r.urgency} /></td>
                <td className="td max-w-xs truncate">{r.summary}{r.case_id && <Link href={`/cases/${r.case_id}`} className="ms-2 text-xs underline">Case</Link>}</td>
              </tr>))}</tbody></table>
        )}
        {data && <Pager page={f.page} size={f.size} total={data.total} onPage={(p) => setF({ ...f, page: p })} />}
      </div>
    </>
  );
}

export default function Page() { return <Suspense><Inbox /></Suspense>; }

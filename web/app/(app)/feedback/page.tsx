"use client";
import Link from "next/link";
import { useState } from "react";
import { api, qs } from "@/lib/api";
import { Badge, Empty, ErrorBox, PageHead, Pager, Skeleton, fmt, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";

export default function Inbox() {
  const [f, setF] = useState<any>({ page: 1, size: 15, sort: "created_at", order: "desc" });
  const [sel, setSel] = useState<string[]>([]);
  const toast = useToast();
  const depts = useFetch<any[]>("/departments");
  const themes = useFetch<any>("/settings/themes");
  const { data, loading, error, reload } = useFetch<any>("/feedback" + qs(f), [JSON.stringify(f)]);
  const set = (k: string, v: any) => setF({ ...f, [k]: v, page: 1 });
  const sort = (k: string) => setF({ ...f, sort: k, order: f.sort === k && f.order === "desc" ? "asc" : "desc" });
  const Th = ({ k, children }: any) => <th className="th cursor-pointer select-none" onClick={() => sort(k)}>{children}{f.sort === k ? (f.order === "desc" ? " ↓" : " ↑") : ""}</th>;
  return (
    <>
      <PageHead title="Feedback inbox" sub="Post-discharge responses, newest first">
        {sel.length > 0 && <button className="btn btn-ghost" onClick={async () => { await api("/feedback/bulk-review", { body: { ids: sel } }); toast(`${sel.length} marked reviewed`); setSel([]); reload(); }}>Mark {sel.length} reviewed</button>}
      </PageHead>
      <div className="card p-3 mb-4 grid grid-cols-2 md:grid-cols-6 gap-2">
        <input className="input" placeholder="Search text…" onChange={(e) => set("q", e.target.value)} aria-label="Search" />
        <select className="input" onChange={(e) => set("department_id", e.target.value)} aria-label="Department"><option value="">All departments</option>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
        <select className="input" onChange={(e) => set("rating", e.target.value)} aria-label="Rating"><option value="">Any rating</option>{[5, 4, 3, 2, 1].map((r) => <option key={r}>{r}</option>)}</select>
        <select className="input" onChange={(e) => set("sentiment", e.target.value)} aria-label="Sentiment"><option value="">Any sentiment</option><option>positive</option><option>neutral</option><option>negative</option></select>
        <select className="input" onChange={(e) => set("theme", e.target.value)} aria-label="Theme"><option value="">Any theme</option>{themes.data?.value.map((t: string) => <option key={t}>{t}</option>)}</select>
        <select className="input" onChange={(e) => set("language", e.target.value)} aria-label="Language"><option value="">Any language</option><option value="en">English</option><option value="ar">Arabic</option></select>
      </div>
      <div className="card overflow-x-auto">
        {loading ? <Skeleton /> : error ? <ErrorBox msg={error} retry={reload} /> : data.items.length === 0 ? <Empty title="No feedback matches these filters" hint="Clear a filter, or send a discharge event from Admin → Integrations to collect a new response." /> : (
          <table className="w-full"><thead><tr><th className="th w-8"></th><Th k="created_at">Received</Th><th className="th">Patient</th><th className="th">Dept</th><Th k="rating">Rating</Th><Th k="sentiment">Sentiment</Th><th className="th">Themes</th><Th k="urgency">Urgency</Th><th className="th">Summary</th></tr></thead>
            <tbody>{data.items.map((r: any) => (
              <tr key={r.id} className="hover:bg-black/5">
                <td className="td"><input type="checkbox" aria-label="Select" checked={sel.includes(r.id)} onChange={(e) => setSel(e.target.checked ? [...sel, r.id] : sel.filter((x) => x !== r.id))} /></td>
                <td className="td whitespace-nowrap">{fmt(r.created_at)}</td>
                <td className="td"><Link className="underline" href={`/feedback/${r.id}`}>{r.patient}</Link>{r.language === "ar" && <span className="ms-1 text-xs">AR</span>}</td>
                <td className="td">{r.department}</td>
                <td className="td">{"★".repeat(r.rating)}<span style={{ opacity: 0.25 }}>{"★".repeat(5 - r.rating)}</span></td>
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

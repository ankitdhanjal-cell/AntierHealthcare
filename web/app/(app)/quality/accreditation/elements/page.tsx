"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { qs } from "@/lib/api";
import { Badge, Empty, ErrorBox, PageHead, Skeleton, fmtDate, useFetch } from "@/components/ui";

function Elements() {
  const sp = useSearchParams();
  const [f, setF] = useState<any>({ status: sp.get("status") || "", mine: sp.get("mine") || "", q: "" });
  const { data, loading, error, reload } = useFetch<any[]>("/accreditation/elements" + qs(f), [JSON.stringify(f)]);
  return (
    <>
      <PageHead title="All standard elements" sub="Every measurable element across the sample standards library" />
      <div className="card p-3 mb-4 flex flex-wrap gap-2">
        <input className="input !w-64" placeholder="Search elements…" aria-label="Search" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
        <select className="input !w-44" aria-label="Status" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">Any status</option>{["Met", "Partially met", "Not met", "Not applicable"].map((s) => <option key={s}>{s}</option>)}</select>
        <label className="text-sm flex items-center gap-1"><input type="checkbox" checked={!!f.mine} onChange={(e) => setF({ ...f, mine: e.target.checked ? "true" : "" })} /> Assigned to me</label>
      </div>
      <div className="card overflow-x-auto">
        {loading ? <Skeleton /> : error ? <ErrorBox msg={error} retry={reload} /> : !data?.length ? <Empty title="No elements match" hint="Clear a filter to see all elements." /> :
          <table className="w-full"><thead><tr><th className="th">Element</th><th className="th">Chapter</th><th className="th">Status</th><th className="th">Owner</th><th className="th">Reviewed</th></tr></thead>
            <tbody>{data.map((e) => <tr key={e.id}><td className="td min-w-[20rem]"><Link className="underline font-medium" href={`/quality/accreditation/elements/${e.id}`}>{e.code}</Link> {e.text}</td><td className="td whitespace-nowrap">{e.chapter}</td>
              <td className="td"><Badge k={e.status} /></td><td className="td">{e.owner}</td><td className="td whitespace-nowrap">{fmtDate(e.last_reviewed_at)}</td></tr>)}</tbody></table>}
      </div>
    </>
  );
}
export default function Page() { return <Suspense><Elements /></Suspense>; }

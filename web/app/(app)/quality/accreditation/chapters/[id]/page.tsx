"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Badge, ErrorBox, PageHead, PctBar, Skeleton, fmtDate, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

export default function Chapter() {
  const { id } = useParams<{ id: string }>(); const me = useMe(); const toast = useToast(); const router = useRouter();
  const { data, loading, error, reload } = useFetch<any>(`/accreditation/chapters/${id}`);
  if (loading && !data) return <Skeleton rows={6} />;
  if (error || !data) return <ErrorBox msg={error} retry={reload} />;
  const canEdit = can(me, "accreditation", "create");
  return (
    <>
      <PageHead title={`${data.code} · ${data.name}`} sub={`${data.readiness.met} of ${data.readiness.applicable} applicable elements met (${data.readiness.pct}%)`}>
        {canEdit && <button className="btn" onClick={async () => { const t = await api("/accreditation/tracers", { body: { chapter_id: id } }); router.push(`/quality/accreditation/tracer/${t.id}`); }}>Start mock survey</button>}
      </PageHead>
      <div className="max-w-md mb-4"><PctBar pct={data.readiness.pct} /></div>
      {data.standards.map((s: any) => (
        <div key={s.code} className="card mb-4">
          <div className="p-4 pb-2"><h2 className="font-medium text-sm">{s.code} · {s.title}</h2></div>
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Element</th><th className="th">Status</th><th className="th">Owner</th><th className="th">Evidence</th><th className="th">Reviewed</th></tr></thead>
            <tbody>{s.elements.map((e: any) => (
              <tr key={e.id}><td className="td min-w-[20rem]"><Link className="underline font-medium" href={`/quality/accreditation/elements/${e.id}`}>{e.code}</Link> {e.text}</td>
                <td className="td">{canEdit ? <select className="input !w-40" aria-label={`Status of ${e.code}`} value={e.status} onChange={(ev) => api(`/accreditation/elements/${e.id}`, { method: "PUT", body: { status: ev.target.value } }).then(() => { toast(`${e.code} marked ${ev.target.value}`); reload(); }).catch((x) => toast(x.message, "err"))}>
                  {["Met", "Partially met", "Not met", "Not applicable"].map((o) => <option key={o}>{o}</option>)}</select> : <Badge k={e.status} />}</td>
                <td className="td">{e.owner}</td><td className="td tabular-nums">{e.evidence_count}{e.status === "Met" && e.evidence_count === 0 && <span className="ms-1 text-xs text-amber-700">none</span>}</td>
                <td className="td whitespace-nowrap" style={e.review_overdue ? { color: "#d97706" } : {}}>{fmtDate(e.last_reviewed_at)}</td></tr>))}</tbody></table></div>
        </div>))}
    </>
  );
}

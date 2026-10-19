"use client";
import { Badge, Empty, ErrorBox, PageHead, Skeleton, fmt, useFetch } from "@/components/ui";
import { ExportBar } from "@/components/ExportBar";
export default function Reviews() {
  const { data, loading, error, reload } = useFetch<any[]>("/feedback/review-requests");
  return (
    <>
      <PageHead title="Review requests" sub="Satisfied patients are invited to share their experience on Google. Unhappy patients are never blocked from posting.">
        <ExportBar filename="review-requests" rows={data || []} columns={[["Patient", (r) => r.patient], ["Invited", (r) => fmt(r.invited_at)], ["Clicked through", (r) => (r.clicked ? "Yes" : "No")]]} /></PageHead>
      <div className="card overflow-x-auto">
        {loading ? <Skeleton /> : error ? <ErrorBox msg={error} retry={reload} /> : !data?.length ? <Empty title="No review invitations yet" hint="When a patient gives a happy response, the Google invitation appears here." /> :
          <table className="w-full"><thead><tr><th className="th">Patient</th><th className="th">Invited</th><th className="th">Status</th></tr></thead>
            <tbody>{data.map((r) => <tr key={r.id}><td className="td">{r.patient}</td><td className="td">{fmt(r.invited_at)}</td><td className="td">{r.clicked ? <Badge k="green">Clicked</Badge> : <Badge k="neutral">Not clicked</Badge>}</td></tr>)}</tbody></table>}
      </div>
    </>
  );
}

"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PatientPreviewPair } from "@/components/PatientPreview";
import { api } from "@/lib/api";
import { AiTag, Badge, ErrorBox, PageHead, Skeleton, fmt, useFetch } from "@/components/ui";
import { useToast } from "@/components/Providers";
import { can, useMe } from "@/components/Shell";

export default function Detail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter(); const toast = useToast(); const me = useMe();
  const { data, loading, error, reload } = useFetch<any>(`/feedback/${id}`);
  const themes = useFetch<any>("/settings/themes");
  const [tags, setTags] = useState<any>(null); const [showPatient, setShowPatient] = useState(false);
  useEffect(() => { if (data) setTags({ sentiment: data.sentiment, themes: data.themes, urgency: data.urgency }); }, [data]);
  if (loading || !tags) return <Skeleton rows={6} />;
  if (error) return <ErrorBox msg={error} retry={reload} />;
  const ai = data.ai || {}; const rtl = data.language === "ar";
  const toggle = (t: string) => setTags({ ...tags, themes: tags.themes.includes(t) ? tags.themes.filter((x: string) => x !== t) : [...tags.themes, t] });
  return (
    <>
      <PageHead title={`Feedback from ${data.patient}`} sub={`${fmt(data.created_at)} · ${data.department}${data.channel === "qr" ? " · ward or clinic QR code" : data.channel === "sms" ? " · SMS" : ""}`}>
        {data.case ? <Link className="btn" href={`/cases/${data.case.id}`}>Open case {data.case.number}</Link> :
          can(me, "cases", "create") && <button className="btn" onClick={async () => { const r = await api(`/feedback/${id}/open-case`, { body: {} }); toast("Case opened"); router.push(`/cases/${r.case_id}`); }}>Open case</button>}
      </PageHead>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between"><div className="text-lg">{"★".repeat(data.rating)}<span style={{ opacity: 0.25 }}>{"★".repeat(5 - data.rating)}</span></div>
            {data.nps != null && <div className="text-sm"><span style={{ color: "var(--muted)" }}>Likelihood to recommend </span><b className="tabular-nums">{data.nps}/10</b> <Badge k={data.nps >= 9 ? "green" : data.nps >= 7 ? "neutral" : "red"}>{data.nps >= 9 ? "Promoter" : data.nps >= 7 ? "Passive" : "Detractor"}</Badge></div>}</div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs" style={{ color: "var(--muted)" }}>
            {data.mrn && <><dt>MRN</dt><dd className="text-[var(--ink)]">{data.mrn}</dd></>}{data.ward && <><dt>Ward and bed</dt><dd className="text-[var(--ink)]">{data.ward}</dd></>}
            {data.attending && <><dt>Attending doctor</dt><dd className="text-[var(--ink)]">{data.attending}</dd></>}{data.length_of_stay_days != null && <><dt>Length of stay</dt><dd className="text-[var(--ink)]">{data.length_of_stay_days} days</dd></>}</dl>
          <div><div className="label">Original comment {rtl && "(Arabic)"}</div><p dir={rtl ? "rtl" : "ltr"} className="text-sm">{data.text || "No comment left."}</p></div>
          {ai.translation_en && rtl && <div><div className="label">English translation <AiTag /></div><p className="text-sm">{ai.translation_en}</p></div>}
          {data.staff_mentions?.length > 0 && <div><div className="label">Staff named in the comment</div><div className="flex flex-wrap gap-1.5">{data.staff_mentions.map((s: string) => <Badge key={s} k="green">{s}</Badge>)}</div>
            {data.sentiment === "positive" && can(me, "feedback", "create") && (data.compliment_shared_at ? <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Shared with the department on {fmt(data.compliment_shared_at)}.</p> :
              <button className="btn btn-ghost mt-2" onClick={async () => { try { const r = await api(`/feedback/${id}/share-compliment`, { body: {} }); toast(`Shared with ${r.shared_with}`); reload(); } catch (e: any) { toast(e.message, "err"); } }}>Share with the department head</button>)}</div>}
          <div><div className="label">Question scores</div><div className="flex gap-2 flex-wrap text-xs">{Object.entries(data.answers).map(([k, v]) => <span key={k} className="px-2 py-0.5 rounded" style={{ background: "var(--line)" }}>{k}: {v as number}/5</span>)}</div></div>
        </div>
        <div className="card p-4 space-y-3">
          <div className="font-medium text-sm">AI analysis <AiTag /> {data.ai_status === "needs_review" && <Badge k="amber">Needs review</Badge>}</div>
          <div><div className="label">One-line summary</div><p className="text-sm">{ai.summary}</p></div>
          <div><div className="label">Suggested owner</div><p className="text-sm">{ai.suggested_owner}</p></div>
          <div><div className="label">Sentiment</div><select className="input" value={tags.sentiment} onChange={(e) => setTags({ ...tags, sentiment: e.target.value })}><option>positive</option><option>neutral</option><option>negative</option></select></div>
          <div><div className="label">Urgency</div><select className="input" value={tags.urgency} onChange={(e) => setTags({ ...tags, urgency: e.target.value })}><option>high</option><option>medium</option><option>low</option></select></div>
          <div><div className="label">Themes</div><div className="flex flex-wrap gap-1.5">{themes.data?.value.map((t: string) => <button key={t} type="button" onClick={() => toggle(t)} className="px-2 py-1 rounded-full text-xs border" style={tags.themes.includes(t) ? { background: "var(--brand)", color: "#fff" } : { borderColor: "var(--line)" }}>{t}</button>)}</div>
            {(ai.new_themes || []).length > 0 && <p className="text-xs mt-1">Proposed new theme: {ai.new_themes.join(", ")} <Badge k="new">new</Badge></p>}</div>
          {can(me, "feedback", "create") && <button className="btn" onClick={async () => { await api(`/feedback/${id}/tags`, { method: "PUT", body: tags }); toast("Tags saved. AI suggestion and your values are both stored."); reload(); }}>{data.reviewed ? "Update tags" : "Accept / save tags"}</button>}
        </div>
      </div>
      <div className="card p-4 mt-4">
        <div className="flex justify-between items-center"><div><h2 className="font-medium text-sm">What the patient saw</h2><p className="text-xs" style={{ color: "var(--muted)" }}>The WhatsApp message and the form on their phone, in English and Arabic (sample name).</p></div>
          <button className="btn btn-ghost" onClick={() => setShowPatient(!showPatient)}>{showPatient ? "Hide" : "Show"}</button></div>
        {showPatient && <div className="mt-4"><PatientPreviewPair /></div>}
      </div>
    </>
  );
}

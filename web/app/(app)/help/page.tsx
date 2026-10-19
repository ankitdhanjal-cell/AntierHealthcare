"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHead } from "@/components/ui";

type Article = { id: string; title: string; summary: string; body: React.ReactNode };

const ARTICLES: Article[] = [
  { id: "incident", title: "Reporting an incident", summary: "Takes about a minute, and it can be anonymous.", body: (
    <>
      <p>Open <b>Quality → Report an incident</b>. Describe what happened in plain words: what, where and when. You do not need to name anyone.</p>
      <ol><li>Write what happened, then choose <b>Suggest category and harm level</b> if you want help. You can change the suggestion.</li>
        <li>Pick the department and say where it happened (ward, room, bed).</li><li>Choose the harm level: <b>near miss</b> (caught before reaching the patient), <b>no harm</b>, <b>mild</b>, <b>moderate</b>, <b>severe</b> or <b>death</b>.</li>
        <li>Add the immediate action you took. Tick <b>Report anonymously</b> if you prefer, and your name is not stored.</li></ol>
      <p>The Quality team triages every report. Serious events (severe harm or death) are flagged red, have a 72-hour investigation deadline, and are escalated to management.</p>
    </>) },
  { id: "audit", title: "Running an audit on the ward", summary: "Yes, No or N/A on your phone, with a photo if you need one.", body: (
    <>
      <p>Open <b>Quality → Audits</b> and choose a scheduled audit that is assigned to you, then <b>Start</b>.</p>
      <ol><li>Answer each question <b>Yes</b>, <b>No</b> or <b>N/A</b>. Your answers save as you go.</li><li>For a No, add a short comment and, if useful, a photo from your phone camera.</li>
        <li>When every question is answered, add a summary comment and choose <b>Complete audit</b>.</li><li>On the result page, any No can become a <b>corrective action</b> in one click. Completed audits can be attached as evidence for an accreditation element.</li></ol>
      <p>Compliance is the number of Yes answers divided by Yes plus No. N/A answers are left out.</p>
    </>) },
  { id: "case", title: "Closing a complaint case", summary: "Call the patient back, record the outcome, then close.", body: (
    <>
      <p>Cases open automatically when feedback is not a happy one. Each has a due time based on its urgency.</p>
      <ol><li>Open the case and use <b>Call patient</b> to record the outcome: reached, apologised, resolved, follow-up needed, or no answer.</li><li>Add notes as you investigate. If the complaint describes a safety event, choose <b>Raise incident</b>.</li>
        <li>Write a resolution note and choose <b>Resolve</b> or <b>Close</b>. A resolution note is required.</li><li>Optionally send the patient a closing message. A case shows <b>Loop closed</b> once it is closed and the patient was spoken to.</li></ol>
    </>) },
  { id: "survey", title: "Preparing for an accreditation survey", summary: "Readiness, evidence and a mock survey of each chapter.", body: (
    <>
      <p>Open <b>Quality → Accreditation</b>. The page shows how many applicable elements are met, the days left to the survey, and every open gap with its owner.</p>
      <ol><li>Give each element an owner and keep its status honest: Met, Partially met, Not met or Not applicable.</li><li>Attach evidence: upload a policy or record, or attach a completed corrective action or audit with one click.</li>
        <li>Run a <b>mock survey</b> of a chapter. Walk each element, record what you find, and turn any finding into an action with <b>Create action</b>.</li><li>Export the monthly <b>committee pack</b> from <b>Quality → Committee reports</b> to show progress.</li></ol>
      <p>The standards in this product are a generic sample set. Load your own programme's standards before a real survey.</p>
    </>) },
  { id: "runchart", title: "Reading a run chart", summary: "Median, target, and what a shift means.", body: (
    <>
      <p>Open <b>Quality → Indicators</b> and choose an indicator. The chart shows the last twelve completed months.</p>
      <ul><li>The <b>solid line</b> is the target. The <b>dashed line</b> is the median of the points shown.</li><li>A <b>shift</b> is six or more points in a row on the same side of the median. It is a real change, not normal variation, and is marked in red when it is getting worse.</li>
        <li>Every indicator has a definition, numerator, denominator, target, data source and owner on its page.</li></ul>
      <p>Some indicators are calculated from records. Others are entered once a month under <b>Enter monthly values</b>.</p>
    </>) },
  { id: "qr", title: "QR codes and SMS for feedback", summary: "More ways for patients to tell you about their visit.", body: (
    <>
      <p>Patients normally get a WhatsApp message after discharge. Two more routes are available.</p>
      <ul><li><b>QR codes:</b> open <b>Admin → Settings → Feedback channels</b>, then print the code for each ward or clinic. Scanning opens the same English and Arabic form.</li>
        <li><b>SMS:</b> when sending a discharge event from <b>Admin → Integrations</b>, choose SMS. The patient receives a short text with the same link.</li></ul>
      <p>Satisfied patients are invited to review the hospital on Google. Patients who are unhappy get a thank-you and a call-back, and nothing stops anyone from posting publicly.</p>
      <p><Link className="underline" href="/admin/settings">Go to Settings</Link></p>
    </>) },
];

export default function Help() {
  const [id, setId] = useState(ARTICLES[0].id);
  useEffect(() => { const h = window.location.hash.slice(1); if (ARTICLES.some((a) => a.id === h)) setId(h); }, []);
  const a = ARTICLES.find((x) => x.id === id)!;
  return (
    <>
      <PageHead title="Help" sub="Short guides for the things you do every week" />
      <div className="grid grid-cols-1 md:grid-cols-[16rem_1fr] gap-4">
        <nav aria-label="Help articles" className="card p-2 h-fit">{ARTICLES.map((x) => (
          <button key={x.id} onClick={() => { setId(x.id); history.replaceState(null, "", `#${x.id}`); }} className="block w-full text-start px-3 py-2 rounded-md text-sm" style={x.id === id ? { background: "var(--brand)", color: "#fff" } : {}}>
            <span className="block font-medium">{x.title}</span><span className="block text-xs opacity-80">{x.summary}</span></button>))}</nav>
        <article className="card p-6 text-sm leading-relaxed max-w-3xl [&_ol]:list-decimal [&_ol]:ps-5 [&_ul]:list-disc [&_ul]:ps-5 [&_li]:mb-1.5 [&_p]:mb-3 space-y-1"><h2 className="text-lg font-semibold mb-2">{a.title}</h2>{a.body}</article>
      </div>
    </>
  );
}

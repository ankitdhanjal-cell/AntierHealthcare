"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { T } from "@/lib/i18n";

export default function PatientForm() {
  const { token } = useParams<{ token: string }>();
  const [form, setForm] = useState<any>(null);
  const [lang, setLang] = useState("en");
  const [rating, setRating] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [clicked, setClicked] = useState(false);
  useEffect(() => {
    api(`/public/feedback/${token}`, { auth: false }).then((f) => { setForm(f); setLang(f.language); if (f.primary_color) document.documentElement.style.setProperty("--brand", f.primary_color); }).catch((e) => setErr(e.message));
  }, [token]);
  useEffect(() => { if (form?.branding?.primary_color) document.documentElement.style.setProperty("--brand", form.branding.primary_color); }, [form]);
  const t = T[lang]; const rtl = lang === "ar";
  if (err && !form) return <div className="p-8 text-center text-sm">{err}</div>;
  if (!form) return <div className="p-6"><div className="skeleton h-40" /></div>;
  const b = form.branding;
  async function submit() {
    if (!rating) return setErr(lang === "ar" ? "يرجى اختيار تقييم بالنجوم." : "Please choose a star rating.");
    setBusy(true); setErr("");
    try { setResult(await api(`/public/feedback/${token}`, { body: { rating, answers, text, language: lang }, auth: false })); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div dir={rtl ? "rtl" : "ltr"} className="min-h-screen max-w-md mx-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">{b.logo_url ? <img src={b.logo_url} className="h-8" alt="" /> : <div className="w-8 h-8 rounded-lg text-white flex items-center justify-center font-bold" style={{ background: "var(--brand)" }}>+</div>}<span className="font-semibold text-sm">{b.hospital}</span></div>
        <button className="text-xs underline" onClick={() => setLang(lang === "ar" ? "en" : "ar")}>{lang === "ar" ? "English" : "العربية"}</button>
      </div>
      {result ? (
        <div className="card p-6 text-center space-y-4">
          {result.google ? <>
            <div className="text-3xl">★</div><h1 className="font-semibold text-lg">{t.googleTitle}</h1><p className="text-sm">{t.googleBody}</p>
            {clicked ? <p className="text-sm text-emerald-700">✓ {rtl ? "تم فتح رابط التقييم (محاكاة)" : "Review link opened (simulated)"}</p> :
              <button className="btn w-full justify-center" onClick={() => { api(`/public/feedback/${token}/google-click`, { body: {}, auth: false }); setClicked(true); }}>{t.googleBtn}</button>}
            <p className="text-xs break-all" style={{ color: "var(--muted)" }}>{result.review_url}</p>
            {!clicked && <button className="text-xs underline" onClick={() => setResult({ ...result, google: false })}>{t.skip}</button>}
          </> : <><div className="text-3xl">✓</div><h1 className="font-semibold text-lg">{t.thanks}</h1><p className="text-sm">{result.case_opened ? t.thanksCase : t.thanksBody}</p></>}
        </div>
      ) : form.answered ? <div className="card p-6 text-center text-sm">{t.already}</div> : (
        <div className="card p-5 space-y-5">
          <p className="text-sm">{t.hello} {form.patient_first_name}،</p>
          <div><h1 className="font-semibold mb-2">{t.rate}</h1>
            <div className="flex gap-1 text-3xl" role="radiogroup" aria-label="Rating">{[1, 2, 3, 4, 5].map((n) => <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n} ${t.star}`} onClick={() => setRating(n)} style={{ color: n <= rating ? "#f5a623" : "var(--line)" }}>★</button>)}</div></div>
          {form.questions.map((q: any) => (
            <div key={q.key}><div className="text-sm mb-1">{q.label}</div>
              <div className="flex gap-1">{[1, 2, 3, 4, 5].map((n) => <button key={n} type="button" onClick={() => setAnswers({ ...answers, [q.key]: n })} className="w-9 h-9 rounded-md text-sm border" style={answers[q.key] === n ? { background: "var(--brand)", color: "#fff", borderColor: "var(--brand)" } : { borderColor: "var(--line)" }}>{n}</button>)}</div></div>
          ))}
          <div><label className="text-sm block mb-1" htmlFor="c">{t.comments}</label><textarea id="c" className="input" rows={4} value={text} maxLength={3000} onChange={(e) => setText(e.target.value)} /></div>
          <button type="button" className="btn btn-ghost w-full justify-center" onClick={() => setErr(rtl ? "التسجيل الصوتي غير متاح في هذه البيئة." : "Voice notes are not available in this sandbox.")}>🎙 {t.voice}</button>
          <p className="text-xs" style={{ color: "var(--muted)" }}>{t.consent}</p>
          {err && <p className="text-sm text-red-600" role="alert">{err}</p>}
          <button className="btn w-full justify-center" disabled={busy} onClick={submit}>{busy ? t.analysing : t.submit}</button>
        </div>
      )}
    </div>
  );
}

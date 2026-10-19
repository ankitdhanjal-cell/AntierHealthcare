"use client";
import { useFetch } from "./ui";

function Phone({ lang }: { lang: "en" | "ar" }) {
  const { data } = useFetch<any>(`/public/preview/${lang}`);
  const rtl = lang === "ar";
  return (
    <div className="w-[300px] shrink-0">
      <div className="text-xs mb-1.5 font-medium" style={{ color: "var(--muted)" }}>{rtl ? "Arabic (right to left)" : "English"}</div>
      <div className="rounded-[1.8rem] border-[7px] border-slate-800 bg-white overflow-hidden shadow-lg text-slate-900" style={{ height: 640 }}>
        <div className="bg-[#075e54] text-white px-3 py-1.5 text-xs font-medium">{data ? `${data.branding.sender_name || data.branding.hospital} · WhatsApp` : "WhatsApp"}</div>
        <div className="p-2 bg-[#ece5dd]" dir={rtl ? "rtl" : "ltr"}>
          <div className="bg-white rounded-lg p-2 text-xs shadow-sm whitespace-pre-line">{data?.whatsapp}<div className="mt-1.5 text-[#0a7cff] underline break-all">{data?.link}</div></div>
        </div>
        <iframe title={`Patient form in ${rtl ? "Arabic" : "English"}`} src={`/f/preview?lang=${lang}`} className="w-full border-0" style={{ height: 546 }} />
      </div>
    </div>
  );
}

/** The patient's side of the experience: the WhatsApp message and the form, in English and Arabic. Sample name, nothing is stored. */
export function PatientPreviewPair() {
  return (
    <div className="overflow-x-auto">
      <div className="flex gap-6 justify-center min-w-[640px] py-1"><Phone lang="en" /><Phone lang="ar" /></div>
    </div>
  );
}

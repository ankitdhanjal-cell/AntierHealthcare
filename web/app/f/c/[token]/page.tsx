"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// A printed ward or clinic QR code lands here, then continues to the same form patients get after discharge.
export default function Channel() {
  const { token } = useParams<{ token: string }>(); const router = useRouter(); const [err, setErr] = useState("");
  useEffect(() => {
    const lang = (navigator.language || "en").toLowerCase().startsWith("ar") ? "ar" : "en";
    api(`/public/channel/${token}/start`, { body: { language: lang }, auth: false }).then((r) => router.replace(`/f/${r.token}`)).catch((e) => setErr(e.message));
  }, [token, router]);
  return <div className="p-8 text-center text-sm">{err || "Opening the feedback form…"}</div>;
}

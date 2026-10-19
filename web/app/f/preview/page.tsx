"use client";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { PatientFormView } from "@/components/PatientFormView";

function Preview() {
  const lang = useSearchParams().get("lang") || "en";
  return <PatientFormView previewLang={lang} />;
}
export default function Page() { return <Suspense><Preview /></Suspense>; }

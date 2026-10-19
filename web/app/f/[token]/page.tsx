"use client";
import { useParams } from "next/navigation";
import { PatientFormView } from "@/components/PatientFormView";

export default function Page() {
  const { token } = useParams<{ token: string }>();
  return <PatientFormView token={token} />;
}

"use client";
import { useState } from "react";
import { useToast } from "./Providers";

type Col = [string, (row: any) => any];
const cell = (v: any) => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };

/** Export the list as CSV (all rows that match the current filters) or print it with the hospital header. */
export function ExportBar({ filename, columns, rows, fetchAll }: { filename: string; columns: Col[]; rows?: any[]; fetchAll?: () => Promise<any[]> }) {
  const toast = useToast(); const [busy, setBusy] = useState(false);
  const exportCsv = async () => {
    setBusy(true);
    try {
      const data = fetchAll ? await fetchAll() : rows || [];
      const csv = [columns.map(([h]) => cell(h)).join(","), ...data.map((r) => columns.map(([, f]) => cell(f(r))).join(","))].join("\n");
      const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
      const a = document.createElement("a"); a.href = url; a.download = `${filename}-${new Date().toLocaleDateString("en-CA")}.csv`; a.click(); URL.revokeObjectURL(url);
      toast(`${data.length} rows exported`);
    } catch (e: any) { toast(e.message || "Export failed", "err"); } finally { setBusy(false); }
  };
  return (
    <div className="flex gap-2 no-print">
      <button className="btn btn-ghost" disabled={busy} onClick={exportCsv}>{busy ? "Exporting…" : "Export CSV"}</button>
      <button className="btn btn-ghost" onClick={() => window.print()}>Print</button>
    </div>
  );
}

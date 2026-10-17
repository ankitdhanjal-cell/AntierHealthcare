"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

type Toast = { id: number; msg: string; kind: "ok" | "err" };
const ToastCtx = createContext<(m: string, k?: "ok" | "err") => void>(() => {});
export const useToast = () => useContext(ToastCtx);

type Confirm = { title: string; body: string; label: string; danger?: boolean; resolve: (v: boolean) => void };
const ConfirmCtx = createContext<(o: Omit<Confirm, "resolve">) => Promise<boolean>>(async () => false);
export const useConfirm = () => useContext(ConfirmCtx);

export function Providers({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const toast = useCallback((msg: string, kind: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  const ask = useCallback((o: Omit<Confirm, "resolve">) => new Promise<boolean>((resolve) => setConfirm({ ...o, resolve })), []);
  useEffect(() => {
    fetch("/api/auth/branding").then((r) => r.json()).then((b) => {
      if (b.primary_color) document.documentElement.style.setProperty("--brand", b.primary_color);
    }).catch(() => {});
  }, []);
  return (
    <ToastCtx.Provider value={toast}>
      <ConfirmCtx.Provider value={ask}>
        {children}
        <div className="fixed bottom-4 end-4 z-50 flex flex-col gap-2" aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className={`px-4 py-2.5 rounded-lg text-sm text-white shadow-lg ${t.kind === "ok" ? "bg-emerald-700" : "bg-red-700"}`}>{t.msg}</div>
          ))}
        </div>
        {confirm && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" role="dialog" aria-modal>
            <div className="card p-5 w-full max-w-sm">
              <h3 className="font-semibold">{confirm.title}</h3>
              <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>{confirm.body}</p>
              <div className="flex justify-end gap-2 mt-4">
                <button className="btn btn-ghost" onClick={() => { confirm.resolve(false); setConfirm(null); }}>Cancel</button>
                <button className={`btn ${confirm.danger ? "btn-danger" : ""}`} onClick={() => { confirm.resolve(true); setConfirm(null); }}>{confirm.label}</button>
              </div>
            </div>
          </div>
        )}
      </ConfirmCtx.Provider>
    </ToastCtx.Provider>
  );
}

export function getToken() {
  try { return localStorage.getItem("ahs_token"); } catch { return null; }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem("ahs_token", t) : localStorage.removeItem("ahs_token"); } catch {}
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: any; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["content-type"] = "application/json";
  const tok = getToken();
  if (tok && opts.auth !== false) headers.authorization = `Bearer ${tok}`;
  const r = await fetch(`/api${path}`, { method: opts.method || (opts.body !== undefined ? "POST" : "GET"), headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined });
  if (r.status === 401 && opts.auth !== false && !path.startsWith("/auth/login")) {
    setToken(null);
    if (typeof window !== "undefined" && !location.pathname.startsWith("/login")) location.href = "/login";
  }
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : j.detail?.[0]?.msg || msg; } catch {}
    throw new ApiError(r.status, msg);
  }
  return r.json();
}

export const qs = (o: Record<string, any>) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== null) p.set(k, String(v)); });
  const s = p.toString();
  return s ? `?${s}` : "";
};

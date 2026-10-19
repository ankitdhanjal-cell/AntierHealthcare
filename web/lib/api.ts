export function getToken() {
  try { return localStorage.getItem("ahs_token"); } catch { return null; }
}
/** Last response for each GET path. Pages show it straight away and refresh it in the background, so revisits feel instant. */
export const responseCache = new Map<string, any>();

export function setToken(t: string | null) {
  try { t ? localStorage.setItem("ahs_token", t) : localStorage.removeItem("ahs_token"); } catch {}
  if (!t) { responseCache.clear(); try { sessionStorage.removeItem("ahs_me"); } catch {} }
}

/** The signed-in user, remembered for this tab so pages can start loading their data without waiting for /auth/me. */
export function rememberMe(me: any) { try { sessionStorage.setItem("ahs_me", JSON.stringify(me)); } catch {} }
export function recalledMe(): any | null { try { const v = sessionStorage.getItem("ahs_me"); return v ? JSON.parse(v) : null; } catch { return null; } }

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

/** Fetch every page of a paged list (up to `max` rows) so an export covers the whole filtered list, not just the page on screen. */
export async function fetchAllPages(path: string, params: Record<string, any> = {}, max = 2000): Promise<any[]> {
  const out: any[] = [];
  for (let page = 1; out.length < max; page++) {
    const r = await api<{ total: number; items: any[] }>(path + qs({ ...params, page, size: 100 }));
    out.push(...r.items);
    if (out.length >= r.total || r.items.length === 0) break;
  }
  return out;
}

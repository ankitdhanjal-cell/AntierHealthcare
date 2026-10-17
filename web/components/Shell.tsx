"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "@/lib/api";
import { useToast } from "./Providers";

export type Me = { id: string; name: string; email: string; role: string; role_name: string; permissions: Record<string, string[]>; sees_all: boolean; department_ids: string[]; language: string };
const MeCtx = createContext<Me | null>(null);
export const useMe = () => useContext(MeCtx)!;
export const can = (me: Me, mod: string, act = "view") => (me.permissions[mod] || []).includes(act);

const NAV = [
  { href: "/", label: "Home", mod: "dashboard" },
  { group: "Patient Experience", mod: "feedback", items: [
    { href: "/feedback", label: "Feedback", mod: "feedback" }, { href: "/cases", label: "Cases", mod: "cases" },
    { href: "/feedback/reviews", label: "Review requests", mod: "feedback" }] },
  { group: "Admin", mod: "settings", items: [
    { href: "/admin/integrations", label: "Integrations", mod: "integrations" }, { href: "/admin/users", label: "Users and roles", mod: "users" },
    { href: "/admin/audit", label: "Audit trail", mod: "audit" }, { href: "/admin/settings", label: "Settings", mod: "settings" }] },
] as any[];

export function Shell({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [branding, setBranding] = useState<any>({});
  const [notif, setNotif] = useState<any>({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const path = usePathname();
  const router = useRouter();
  const toast = useToast();

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    api<Me>("/auth/me").then(setMe).catch(() => {});
    api("/auth/branding", { auth: false }).then(setBranding);
  }, [router]);
  useEffect(() => {
    if (!me) return;
    const load = () => api("/notifications").then(setNotif).catch(() => {});
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [me]);
  useEffect(() => {
    if (q.length < 2) { setHits([]); return; }
    const t = setTimeout(() => api("/search?q=" + encodeURIComponent(q)).then(setHits).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [q]);

  if (!me) return <div className="p-8"><div className="skeleton h-8 w-64" /></div>;
  const crumbs = path.split("/").filter(Boolean);

  return (
    <MeCtx.Provider value={me}>
      <div className="flex min-h-screen">
        <aside className="w-60 shrink-0 hidden md:flex flex-col p-4 gap-1" style={{ background: "var(--card)", borderInlineEnd: "1px solid var(--line)" }}>
          <div className="flex items-center gap-2 mb-5 px-2">
            {branding.logo_url ? <img src={branding.logo_url} alt="" className="h-8" /> : <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold" style={{ background: "var(--brand)" }}>+</div>}
            <div className="leading-tight"><div className="text-sm font-semibold">Antier Healthcare Suite</div><div className="text-xs" style={{ color: "var(--muted)" }}>{branding.hospital}</div></div>
          </div>
          {NAV.filter((n) => can(me, n.mod)).map((n) =>
            n.href ? <NavLink key={n.href} {...n} path={path} /> : (
              <div key={n.group} className="mt-3">
                <div className="px-2 text-[11px] uppercase tracking-wider mb-1" style={{ color: "var(--muted)" }}>{n.group}</div>
                {n.items.filter((i: any) => can(me, i.mod)).map((i: any) => <NavLink key={i.href} {...i} path={path} />)}
              </div>
            ))}
          <div className="mt-auto text-xs px-2" style={{ color: "var(--muted)" }}>Version {branding.version}</div>
        </aside>
        <div className="flex-1 min-w-0 flex flex-col">
          <header className="flex items-center gap-3 px-6 py-3" style={{ background: "var(--card)", borderBottom: "1px solid var(--line)" }}>
            <div className="relative flex-1 max-w-md">
              <input className="input" placeholder="Search cases, feedback, patients…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Global search" />
              {q.length >= 2 && (
                <div className="absolute z-30 mt-1 w-full card shadow-lg max-h-80 overflow-auto">
                  {hits.length === 0 ? <div className="p-3 text-sm" style={{ color: "var(--muted)" }}>No matches for “{q}”</div> :
                    hits.map((h, i) => <Link key={i} href={h.href} onClick={() => setQ("")} className="block px-3 py-2 text-sm hover:bg-black/5"><span className="text-xs me-2" style={{ color: "var(--muted)" }}>{h.type}</span>{h.title}</Link>)}
                </div>
              )}
            </div>
            <span className="ms-auto px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800" title="This is a sandbox environment">Sandbox</span>
            <div className="relative">
              <button className="btn btn-ghost" aria-label="Notifications" onClick={() => setOpen(!open)}>Notifications{notif.unread > 0 && <span className="px-1.5 rounded-full bg-red-600 text-white text-xs">{notif.unread}</span>}</button>
              {open && (
                <div className="absolute end-0 z-30 mt-1 w-96 card shadow-lg max-h-96 overflow-auto">
                  <div className="flex justify-between p-3 text-sm font-medium" style={{ borderBottom: "1px solid var(--line)" }}>Notification centre
                    <button className="text-xs underline" onClick={() => api("/notifications/read", { method: "POST", body: {} }).then(() => { setNotif({ ...notif, unread: 0 }); toast("All marked as read"); })}>Mark all read</button></div>
                  {notif.items.length === 0 ? <div className="p-4 text-sm" style={{ color: "var(--muted)" }}>You're all caught up.</div> :
                    notif.items.map((n: any) => <Link key={n.id} href={n.link || "#"} onClick={() => setOpen(false)} className="block px-3 py-2 text-sm hover:bg-black/5" style={{ opacity: n.read ? 0.6 : 1 }}><div className="font-medium">{n.title}</div><div className="text-xs" style={{ color: "var(--muted)" }}>{n.body}</div></Link>)}
                </div>
              )}
            </div>
            <div className="text-sm text-end leading-tight"><div>{me.name}</div><div className="text-xs" style={{ color: "var(--muted)" }}>{me.role_name}</div></div>
            <button className="btn btn-ghost" onClick={() => { setToken(null); router.replace("/login"); }}>Sign out</button>
          </header>
          <main className="p-6 flex-1">
            <nav className="text-xs mb-3" style={{ color: "var(--muted)" }} aria-label="Breadcrumb">
              <Link href="/">Home</Link>{crumbs.map((c, i) => <span key={i}> / <Link href={"/" + crumbs.slice(0, i + 1).join("/")}>{c.length > 14 ? "details" : c}</Link></span>)}
            </nav>
            {children}
          </main>
          <footer className="px-6 py-3 text-xs flex justify-between" style={{ color: "var(--muted)", borderTop: "1px solid var(--line)" }}>
            <span>Antier Healthcare Suite · Version {branding.version}</span><Link href="/profile">Profile and password</Link>
          </footer>
        </div>
      </div>
    </MeCtx.Provider>
  );
}

function NavLink({ href, label, path }: { href: string; label: string; path: string }) {
  const active = href === "/" ? path === "/" : path === href || (path.startsWith(href + "/") && href !== "/feedback");
  return <Link href={href} className="block px-2 py-1.5 rounded-md text-sm" style={active ? { background: "var(--brand)", color: "#fff" } : {}}>{label}</Link>;
}

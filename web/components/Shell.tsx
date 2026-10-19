"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "@/lib/api";
import { useToast } from "./Providers";
import { setHospitalTz } from "./ui";

export type Me = { id: string; name: string; email: string; role: string; role_name: string; permissions: Record<string, string[]>; sees_all: boolean; department_ids: string[]; language: string; theme: string };
const MeCtx = createContext<Me | null>(null);
export const useMe = () => useContext(MeCtx)!;
export const can = (me: Me, mod: string, act = "view") => (me.permissions[mod] || []).includes(act);

const NAV = [
  { href: "/", label: "Home", mod: "dashboard" },
  { group: "Patient Experience", mod: "feedback", items: [
    { href: "/feedback", label: "Feedback", mod: "feedback" }, { href: "/cases", label: "Cases", mod: "cases" },
    { href: "/feedback/reviews", label: "Review requests", mod: "feedback" },
    { href: "/feedback/nps", label: "Recommend score (NPS)", mod: "feedback" }, { href: "/feedback/compliments", label: "Compliments", mod: "feedback" }] },
  { group: "Quality", mod: "incidents", items: [
    { href: "/quality/incidents", label: "Incidents", mod: "incidents" }, { href: "/quality/incidents/new", label: "Report an incident", mod: "incidents", create: true },
    { href: "/quality/accreditation", label: "Accreditation", mod: "accreditation" },
    { href: "/quality/audits", label: "Audits", mod: "audits" }, { href: "/quality/indicators", label: "Indicators", mod: "indicators" },
    { href: "/quality/actions", label: "Actions register", mod: "incidents" }, { href: "/quality/reports", label: "Committee reports", mod: "reports" }] },
  { group: "Admin", mod: "settings", items: [
    { href: "/admin/integrations", label: "Integrations", mod: "integrations" }, { href: "/admin/users", label: "Users and roles", mod: "users" },
    { href: "/admin/audit", label: "Audit trail", mod: "audit" }, { href: "/admin/settings", label: "Settings", mod: "settings" }] },
] as any[];

// Page titles for breadcrumbs, from the nav plus the pages that are not in it
const TITLES: Record<string, string> = { admin: "Admin", feedback: "Feedback", cases: "Cases", reviews: "Review requests", integrations: "Integrations", users: "Users and roles",
  audit: "Audit trail", settings: "Settings", profile: "Profile", quality: "Quality", incidents: "Incidents", new: "Report an incident", accreditation: "Accreditation", chapters: "Chapters", elements: "Elements", tracer: "Mock survey", audits: "Audits", runs: "Audit", templates: "Templates", indicators: "Indicators", entry: "Monthly entry", actions: "Actions register", reports: "Committee reports", nps: "Recommend score (NPS)", compliments: "Compliments", help: "Help" };
const crumbLabel = (seg: string) => TITLES[seg] || (seg.length > 14 ? "Details" : seg.charAt(0).toUpperCase() + seg.slice(1));

// Menu and header text in Arabic. Page content stays in English for staff; patient-facing screens are fully bilingual.
const AR: Record<string, string> = {
  Home: "الرئيسية", "Patient Experience": "تجربة المريض", Feedback: "الملاحظات", Cases: "الحالات", "Review requests": "طلبات التقييم", "Recommend score (NPS)": "مؤشر التوصية (NPS)", Compliments: "الإشادات",
  Quality: "الجودة", Incidents: "الحوادث", "Report an incident": "الإبلاغ عن حادثة", Accreditation: "الاعتماد", Audits: "التدقيق", Indicators: "المؤشرات", "Actions register": "سجل الإجراءات",
  "Committee reports": "تقارير اللجنة", Admin: "الإدارة", Integrations: "التكاملات", "Users and roles": "المستخدمون والأدوار", "Audit trail": "سجل التدقيق", Settings: "الإعدادات",
  "Search cases, feedback, patients…": "ابحث في الحالات والملاحظات والمرضى…", Notifications: "الإشعارات", "Sign out": "تسجيل الخروج", Help: "المساعدة", "Profile and password": "الملف الشخصي وكلمة المرور", Version: "الإصدار",
};
export const applyLang = (l?: string) => { document.documentElement.lang = l === "ar" ? "ar" : "en"; document.documentElement.dir = l === "ar" ? "rtl" : "ltr"; };

export const applyTheme = (t?: string) => { document.documentElement.dataset.theme = t === "dark" ? "dark" : "light"; };

export function Shell({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [branding, setBranding] = useState<any>({});
  const [notif, setNotif] = useState<any>({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const [lang, setLang] = useState("en");
  const tr = (s: string) => (lang === "ar" ? AR[s] ?? s : s);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const path = usePathname();
  const router = useRouter();
  const toast = useToast();

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    api<Me>("/auth/me").then((m) => { setMe(m); applyTheme(m.theme); setLang(m.language === "ar" ? "ar" : "en"); applyLang(m.language); }).catch(() => {});
    api("/auth/branding", { auth: false }).then((b) => { setBranding(b); setHospitalTz(b.timezone); });
  }, [router]);
  useEffect(() => {
    if (!me) return;
    const load = () => api("/notifications").then(setNotif).catch(() => {});
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [me]);
  useEffect(() => { setMenu(false); }, [path]);
  useEffect(() => {
    if (q.length < 2) { setHits([]); return; }
    const t = setTimeout(() => api("/search?q=" + encodeURIComponent(q)).then(setHits).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [q]);

  if (!me) return <div className="p-8"><div className="skeleton h-8 w-64" /></div>;
  const crumbs = path.split("/").filter(Boolean);

  const navList = NAV.filter((n) => can(me, n.mod) || can(me, n.mod, "create")).map((n) =>
    n.href ? <NavLink key={n.href} {...n} label={tr(n.label)} path={path} /> : (
      <div key={n.group} className="mt-3">
        <div className="px-2 text-[11px] uppercase tracking-wider mb-1" style={{ color: "var(--muted)" }}>{tr(n.group)}</div>
        {n.items.filter((i: any) => can(me, i.mod, i.create ? "create" : "view")).map((i: any) => <NavLink key={i.href} {...i} label={tr(i.label)} path={path} />)}
      </div>));

  return (
    <MeCtx.Provider value={me}>
      <div className="flex min-h-screen">
        <aside className="w-60 shrink-0 hidden md:flex flex-col p-4 gap-1" style={{ background: "var(--card)", borderInlineEnd: "1px solid var(--line)" }}>
          <div className="flex items-center gap-2 mb-5 px-2">
            {branding.logo_url ? <img src={branding.logo_url} alt="" className="h-8" /> : <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold" style={{ background: "var(--brand)" }}>+</div>}
            <div className="leading-tight"><div className="text-sm font-semibold">Antier Healthcare Suite</div><div className="text-xs" style={{ color: "var(--muted)" }}>{branding.hospital}</div></div>
          </div>
          {navList}
          <div className="mt-auto text-xs px-2" style={{ color: "var(--muted)" }}>{tr("Version")} {branding.version}</div>
        </aside>
        <div className="flex-1 min-w-0 flex flex-col">
          <header className="flex flex-wrap items-center gap-2 md:gap-3 px-3 md:px-6 py-3" style={{ background: "var(--card)", borderBottom: "1px solid var(--line)" }}>
            <button className="btn btn-ghost md:!hidden" aria-label="Open menu" aria-expanded={menu} onClick={() => setMenu(!menu)}>☰ Menu</button>
            <div className="relative flex-1 min-w-[9rem] max-w-md order-last md:order-none basis-full md:basis-auto">
              <input className="input" placeholder={tr("Search cases, feedback, patients…")} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Global search" />
              {q.length >= 2 && (
                <div className="absolute z-30 mt-1 w-full card shadow-lg max-h-80 overflow-auto">
                  {hits.length === 0 ? <div className="p-3 text-sm" style={{ color: "var(--muted)" }}>No matches for “{q}”</div> :
                    hits.map((h, i) => <Link key={i} href={h.href} onClick={() => setQ("")} className="block px-3 py-2 text-sm hover:bg-black/5"><span className="text-xs me-2" style={{ color: "var(--muted)" }}>{h.type}</span>{h.title}</Link>)}
                </div>
              )}
            </div>
            <span className="ms-auto" />
            <Link href="/help" className="btn btn-ghost">{tr("Help")}</Link>
            <button className="btn btn-ghost" aria-label={lang === "ar" ? "Switch to English" : "التبديل إلى العربية"} onClick={() => { const next = lang === "ar" ? "en" : "ar"; setLang(next); applyLang(next); api("/auth/profile", { method: "PUT", body: { language: next } }).catch(() => {}); }}>{lang === "ar" ? "English" : "عربي"}</button>
            <div className="relative">
              <button className="btn btn-ghost" aria-label="Notifications" onClick={() => setOpen(!open)}>{tr("Notifications")}{notif.unread > 0 && <span className="px-1.5 rounded-full bg-red-600 text-white text-xs">{notif.unread}</span>}</button>
              {open && (
                <div className="absolute end-0 z-30 mt-1 w-96 card shadow-lg max-h-96 overflow-auto">
                  <div className="flex justify-between p-3 text-sm font-medium" style={{ borderBottom: "1px solid var(--line)" }}>Notification centre
                    <button className="text-xs underline" onClick={() => api("/notifications/read", { method: "POST", body: {} }).then(() => { setNotif({ ...notif, unread: 0 }); toast("All marked as read"); })}>Mark all read</button></div>
                  {notif.items.length === 0 ? <div className="p-4 text-sm" style={{ color: "var(--muted)" }}>You're all caught up.</div> :
                    notif.items.map((n: any) => <Link key={n.id} href={n.link || "#"} onClick={() => setOpen(false)} className="block px-3 py-2 text-sm hover:bg-black/5" style={{ opacity: n.read ? 0.6 : 1 }}><div className="font-medium">{n.title}</div><div className="text-xs" style={{ color: "var(--muted)" }}>{n.body}</div></Link>)}
                </div>
              )}
            </div>
            <div className="text-sm text-end leading-tight hidden sm:block"><div>{me.name}</div><div className="text-xs" style={{ color: "var(--muted)" }}>{me.role_name}</div></div>
            <button className="btn btn-ghost" onClick={() => { setToken(null); router.replace("/login"); }}>{tr("Sign out")}</button>
          </header>
          {menu && <div className="md:hidden p-3 max-h-[70vh] overflow-auto no-print" style={{ background: "var(--card)", borderBottom: "1px solid var(--line)" }} role="navigation" aria-label="Menu">{navList}</div>}
          <main className="p-3 md:p-6 flex-1">
            <div className="print-head">{branding.logo_url ? <img src={branding.logo_url} alt="" className="h-10" /> : <div className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-lg" style={{ background: "var(--brand)" }}>+</div>}
              <div><div className="font-semibold">{branding.hospital}</div><div className="text-xs">Printed {new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}</div></div></div>
            <nav className="text-xs mb-3" style={{ color: "var(--muted)" }} aria-label="Breadcrumb">
              <Link href="/">Home</Link>{crumbs.map((c, i) => <span key={i}> / <Link href={"/" + crumbs.slice(0, i + 1).join("/")}>{crumbLabel(c)}</Link></span>)}
            </nav>
            {children}
          </main>
          <footer className="px-6 py-3 text-xs flex justify-between" style={{ color: "var(--muted)", borderTop: "1px solid var(--line)" }}>
            <span>Antier Healthcare Suite · {tr("Version")} {branding.version}</span><Link href="/profile">{tr("Profile and password")}</Link>
          </footer>
        </div>
      </div>
    </MeCtx.Provider>
  );
}

function NavLink({ href, label, path }: { href: string; label: string; path: string }) {
  const active = href === "/" ? path === "/" : path === href || (path.startsWith(href + "/") && href !== "/feedback" && href !== "/quality/incidents");
  return <Link href={href} className="block px-2 py-1.5 rounded-md text-sm" style={active ? { background: "var(--brand)", color: "#fff" } : {}}>{label}</Link>;
}

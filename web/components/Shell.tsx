"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AlertTriangle, Bell, ClipboardCheck, FileText, Gauge, Heart, History, HelpCircle, Inbox, LayoutDashboard, LineChart, ListChecks, Menu, MessageSquare, Plug, PlusCircle, Search, Settings, ShieldCheck, Star, Users } from "lucide-react";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, getToken, recalledMe, rememberMe, setToken } from "@/lib/api";
import { useToast } from "./Providers";
import { setHospitalTz } from "./ui";

export type Me = { id: string; name: string; email: string; role: string; role_name: string; permissions: Record<string, string[]>; sees_all: boolean; department_ids: string[]; language: string; theme: string };
const MeCtx = createContext<Me | null>(null);
export const useMe = () => useContext(MeCtx)!;
export const can = (me: Me, mod: string, act = "view") => (me.permissions[mod] || []).includes(act);

const ICONS: Record<string, any> = {
  "/": LayoutDashboard, "/feedback": MessageSquare, "/cases": Inbox, "/feedback/reviews": Star, "/feedback/nps": Gauge, "/feedback/compliments": Heart,
  "/quality/incidents": AlertTriangle, "/quality/incidents/new": PlusCircle, "/quality/accreditation": ShieldCheck, "/quality/audits": ClipboardCheck,
  "/quality/indicators": LineChart, "/quality/actions": ListChecks, "/quality/reports": FileText, "/admin/integrations": Plug, "/admin/users": Users,
  "/admin/audit": History, "/admin/settings": Settings,
};

const NAV = [
  { href: "/", label: "Home", mod: "*" },
  { group: "Patient Experience", mod: "feedback", items: [
    { href: "/feedback", label: "Feedback", mod: "feedback" }, { href: "/cases", label: "Cases", mod: "cases" },
    { href: "/feedback/reviews", label: "Review requests", mod: "feedback" },
    { href: "/feedback/nps", label: "Recommend score (NPS)", mod: "feedback" }, { href: "/feedback/compliments", label: "Compliments", mod: "feedback" }] },
  { group: "Quality", mod: "incidents", items: [
    { href: "/quality/incidents", label: "Incidents", mod: "incidents" }, { href: "/quality/incidents/new", label: "Report an incident", mod: "incidents", create: true },
    { href: "/quality/accreditation", label: "Accreditation", mod: "accreditation" },
    { href: "/quality/audits", label: "Audits", mod: "audits" }, { href: "/quality/indicators", label: "Indicators", mod: "indicators" },
    { href: "/quality/actions", label: "Actions register", mod: "audits" }, { href: "/quality/reports", label: "Committee reports", mod: "reports" }] },
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
  useEffect(() => { const m = recalledMe(); if (m) { setMe(m); applyTheme(m.theme); applyLang(m.language); setLang(m.language === "ar" ? "ar" : "en"); } }, []);
  const [branding, setBranding] = useState<any>({});
  const [notif, setNotif] = useState<any>({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false); const [userMenu, setUserMenu] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null); const userRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!bellRef.current?.contains(e.target as Node)) setOpen(false); if (!userRef.current?.contains(e.target as Node)) setUserMenu(false); };
    document.addEventListener("mousedown", close); return () => document.removeEventListener("mousedown", close);
  }, []);
  const [lang, setLang] = useState("en");
  const tr = (s: string) => (lang === "ar" ? AR[s] ?? s : s);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const path = usePathname();
  const router = useRouter();
  const toast = useToast();

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    api<Me>("/auth/me").then((m) => { rememberMe(m); setMe(m); applyTheme(m.theme); setLang(m.language === "ar" ? "ar" : "en"); applyLang(m.language); }).catch(() => {});
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

  const allowed = (i: any) => i.mod === "*" || can(me, i.mod, i.create ? "create" : "view");
  const navList = NAV.filter((n) => (n.href ? allowed(n) : n.items.some(allowed))).map((n) =>
    n.href ? <NavLink key={n.href} {...n} label={tr(n.label)} path={path} /> : (
      <div key={n.group}>
        <div className="nav-group">{tr(n.group)}</div>
        {n.items.filter(allowed).map((i: any) => <NavLink key={i.href} {...i} label={tr(i.label)} path={path} />)}
      </div>));

  return (
    <MeCtx.Provider value={me}>
      <div className="flex min-h-screen">
        <aside className="w-60 shrink-0 hidden md:flex flex-col px-3 py-4 no-print" style={{ background: "var(--side)" }}>
          <Link href="/" className="flex items-center gap-2.5 mb-2 px-2 pt-1 pb-3" style={{ borderBottom: "1px solid var(--side-line)" }}>
            {branding.logo_url ? <img src={branding.logo_url} alt="" className="h-8" /> : <div className="w-8 h-8 rounded flex items-center justify-center text-white" style={{ background: "var(--brand)" }}><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M6.5 1h3v5.5H15v3H9.5V15h-3V9.5H1v-3h5.5z" fill="currentColor" /></svg></div>}
            <div className="leading-tight min-w-0"><div className="text-[13px] font-semibold text-white truncate">{branding.hospital}</div><div className="text-[11px]" style={{ color: "var(--side-muted)" }}>Healthcare Suite</div></div>
          </Link>
          <nav className="flex-1 overflow-y-auto pe-1" aria-label="Main">{navList}</nav>
          <div className="text-[11px] px-2 pt-3" style={{ color: "var(--side-muted)" }}>{tr("Version")} {branding.version}</div>
        </aside>
        <div className="flex-1 min-w-0 flex flex-col">
          <header className="flex items-center gap-2 px-3 md:px-6 h-14 no-print" style={{ background: "var(--card)", borderBottom: "1px solid var(--line)" }}>
            <button className="icon-btn md:!hidden" aria-label="Open menu" aria-expanded={menu} onClick={() => setMenu(!menu)}><Menu size={19} /></button>
            <div className="relative flex-1 max-w-md">
              <Search size={15} className="absolute top-1/2 -translate-y-1/2 start-3 pointer-events-none" style={{ color: "var(--muted)" }} />
              <input className="input !ps-9" placeholder={tr("Search cases, feedback, patients…")} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Global search" />
              {q.length >= 2 && (
                <div className="absolute z-30 mt-1 w-full card shadow-lg max-h-80 overflow-auto">
                  {hits.length === 0 ? <div className="p-3 text-sm" style={{ color: "var(--muted)" }}>No matches for “{q}”</div> :
                    hits.map((h, i) => <Link key={i} href={h.href} onClick={() => setQ("")} className="menu-item"><span className="text-xs me-2" style={{ color: "var(--muted)" }}>{h.type}</span>{h.title}</Link>)}
                </div>
              )}
            </div>
            <span className="ms-auto" />
            <button className="text-[13px] px-2 py-1 rounded hover:bg-black/5" aria-label={lang === "ar" ? "Switch to English" : "التبديل إلى العربية"} onClick={() => { const next = lang === "ar" ? "en" : "ar"; setLang(next); applyLang(next); api("/auth/profile", { method: "PUT", body: { language: next } }).catch(() => {}); }}>{lang === "ar" ? "English" : "عربي"}</button>
            <Link href="/help" className="icon-btn" aria-label={tr("Help")} title={tr("Help")}><HelpCircle size={18} /></Link>
            <div className="relative" ref={bellRef}>
              <button className="icon-btn" aria-label={tr("Notifications")} title={tr("Notifications")} onClick={() => { setOpen(!open); setUserMenu(false); }}><Bell size={18} />
                {notif.unread > 0 && <span className="absolute top-0.5 end-0.5 min-w-[16px] h-4 px-1 rounded-full text-[10px] leading-4 text-center text-white font-semibold" style={{ background: "var(--bad)" }}>{notif.unread > 99 ? "99+" : notif.unread}</span>}</button>
              {open && (
                <div className="absolute end-0 z-30 mt-1 w-96 max-w-[92vw] card shadow-lg max-h-96 overflow-auto">
                  <div className="flex justify-between p-3 text-sm font-medium" style={{ borderBottom: "1px solid var(--line)" }}>Notifications
                    <button className="text-xs underline" onClick={() => api("/notifications/read", { method: "POST", body: {} }).then(() => { setNotif({ ...notif, unread: 0 }); toast("All marked as read"); })}>Mark all read</button></div>
                  {notif.items.length === 0 ? <div className="p-4 text-sm" style={{ color: "var(--muted)" }}>You're all caught up.</div> :
                    notif.items.map((n: any) => <Link key={n.id} href={n.link || "#"} onClick={() => setOpen(false)} className="menu-item" style={{ opacity: n.read ? 0.6 : 1 }}><div className="font-medium">{n.title}</div><div className="text-xs" style={{ color: "var(--muted)" }}>{n.body}</div></Link>)}
                </div>
              )}
            </div>
            <div className="relative" ref={userRef}>
              <button className="flex items-center gap-2 ps-1 pe-2 py-1 rounded hover:bg-black/5" aria-label="Account menu" aria-expanded={userMenu} onClick={() => { setUserMenu(!userMenu); setOpen(false); }}>
                <span className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold text-white" style={{ background: "var(--brand)" }}>{me.name.split(" ").map((w: string) => w[0]).slice(0, 2).join("")}</span>
                <span className="text-start leading-tight hidden sm:block"><span className="block text-[13px] font-medium">{me.name}</span><span className="block text-[11px]" style={{ color: "var(--muted)" }}>{me.role_name}</span></span></button>
              {userMenu && (
                <div className="absolute end-0 z-30 mt-1 w-52 card shadow-lg py-1">
                  <Link href="/profile" className="menu-item" onClick={() => setUserMenu(false)}>{tr("Profile and password")}</Link>
                  <button className="menu-item" onClick={() => { setToken(null); router.replace("/login"); }}>{tr("Sign out")}</button>
                </div>
              )}
            </div>
          </header>
          {menu && <div className="md:hidden px-3 pb-3 max-h-[70vh] overflow-auto no-print" style={{ background: "var(--side)" }} role="navigation" aria-label="Menu">{navList}</div>}
          <main className="p-4 md:px-8 md:py-6 flex-1 max-w-[1500px] w-full">
            <div className="print-head">{branding.logo_url ? <img src={branding.logo_url} alt="" className="h-10" /> : <div className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-lg" style={{ background: "var(--brand)" }}>+</div>}
              <div><div className="font-semibold">{branding.hospital}</div><div className="text-xs">Printed {new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}</div></div></div>
            <nav className="text-xs mb-2" style={{ color: "var(--muted)" }} aria-label="Breadcrumb">
              <Link href="/">Home</Link>{crumbs.map((c, i) => <span key={i}> › {["admin", "quality"].includes(c) && i < crumbs.length - 1 ? <span>{crumbLabel(c)}</span> : <Link href={"/" + crumbs.slice(0, i + 1).join("/")}>{crumbLabel(c)}</Link>}</span>)}
            </nav>
            {children}
          </main>
          <footer className="px-8 py-3 text-xs no-print" style={{ color: "var(--muted)", borderTop: "1px solid var(--line)" }}>Antier Healthcare Suite · {tr("Version")} {branding.version}</footer>
        </div>
      </div>
    </MeCtx.Provider>
  );
}

function NavLink({ href, label, path }: { href: string; label: string; path: string }) {
  const active = href === "/" ? path === "/" : path === href || (path.startsWith(href + "/") && href !== "/feedback" && href !== "/quality/incidents");
  const Icon = ICONS[href];
  return <Link href={href} className="nav-link" aria-current={active ? "page" : undefined}>{Icon && <Icon size={16} strokeWidth={1.75} className="shrink-0" style={{ opacity: 0.9 }} />}<span className="truncate">{label}</span></Link>;
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  LayoutDashboard,
  ListChecks,
  Layers,
  ReceiptText,
  Users2,
  UploadCloud,
  BarChart3,
  Menu,
  X,
  LogOut,
  Scale,
} from "lucide-react";
import { logout } from "@/lib/api";
import { useMe } from "@/components/Providers";
import Logo, { LogoMark } from "@/components/Logo";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  tag?: string;
}

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Collect",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard },
      { href: "/today", label: "Today", icon: ListChecks, tag: "Lanes" },
      { href: "/queue", label: "Invoice queue", icon: Layers },
    ],
  },
  {
    title: "Books",
    items: [
      { href: "/invoices", label: "Receivables ledger", icon: ReceiptText },
      { href: "/customers", label: "Customers", icon: Users2 },
      { href: "/import", label: "Import", icon: UploadCloud },
    ],
  },
  {
    title: "Insights",
    items: [{ href: "/analytics", label: "Analytics", icon: BarChart3 }],
  },
];

function initials(name?: string) {
  if (!name) return "··";
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function NavList({ pathname, onNavigate }: { pathname: string; onNavigate: () => void }) {
  return (
    <div className="flex-1 px-3 py-4 overflow-y-auto space-y-6">
      {SECTIONS.map((section) => (
        <div key={section.title}>
          <div className="px-3 mb-2 text-[10px] font-mono font-medium tracking-[0.16em] text-sidebar-muted/80 uppercase">
            {section.title}
          </div>
          <nav className="space-y-0.5" aria-label={section.title}>
            {section.items.map((item) => {
              const Icon = item.icon;
              const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={`relative flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-colors duration-150 ${
                    active ? "text-white" : "text-sidebar-muted hover:text-white hover:bg-sidebar-hover/70"
                  }`}
                >
                  {active && (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-0 rounded-xl bg-gradient-to-r from-brand-600/90 to-brand-700/60 ring-1 ring-white/10"
                      transition={{ type: "spring", stiffness: 420, damping: 36 }}
                    />
                  )}
                  <span className="relative flex items-center gap-3">
                    <Icon className={`w-[18px] h-[18px] ${active ? "text-accent-300" : ""}`} />
                    {item.label}
                  </span>
                  {item.tag && (
                    <span
                      className={`relative text-[9px] font-mono uppercase tracking-wide px-1.5 py-0.5 rounded-md ${
                        active
                          ? "bg-white/15 text-white"
                          : "bg-accent-400/10 text-accent-300 border border-accent-400/25"
                      }`}
                    >
                      {item.tag}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>
      ))}

      <div className="mx-1 p-3.5 rounded-xl border border-sidebar-border bg-sidebar-surface/60 space-y-1.5">
        <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-200">
          <Scale className="w-3.5 h-3.5 text-accent-400" />
          How lists are ranked
        </div>
        <p className="text-[11px] leading-relaxed text-sidebar-muted">
          Transparent rules on overdue ₹, payment pattern, age and contact. Weights are assumptions, not yet validated on real outcomes.
        </p>
      </div>
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { me } = useMe();

  useEffect(() => setOpen(false), [pathname]);

  if (pathname.startsWith("/login") || pathname.startsWith("/sign-up")) return null;

  const profile = (
    <div className="p-3 border-t border-sidebar-border">
      <div className="flex items-center justify-between gap-2 p-2 rounded-xl hover:bg-sidebar-hover/60 transition-colors">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-300 to-accent-500 text-ink-900 flex items-center justify-center font-bold text-xs flex-shrink-0">
            {initials(me?.full_name)}
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-100 truncate">{me?.full_name ?? "Signed in"}</p>
            <p className="text-[10px] text-sidebar-muted truncate capitalize">
              {me ? (me.is_demo ? "Demo · read-only" : `${me.role}${me.org_name ? ` · ${me.org_name}` : ""}`) : ""}
            </p>
          </div>
        </div>
        <button
          onClick={() => logout()}
          aria-label="Sign out"
          title="Sign out"
          className="p-2 text-sidebar-muted hover:text-rose-300 hover:bg-sidebar-hover rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile bar */}
      <div className="md:hidden flex items-center justify-between px-4 h-14 bg-sidebar text-white border-b border-sidebar-border sticky top-0 z-40">
        <Link href="/" aria-label="Udhaar Ledger home">
          <Logo size={30} />
        </Link>
        <button
          onClick={() => setOpen(true)}
          className="p-2 rounded-lg text-sidebar-muted hover:text-white hover:bg-sidebar-hover"
          aria-label="Open navigation"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {/* Desktop sidebar */}
      <aside className="hidden md:flex sticky top-0 h-screen w-64 flex-shrink-0 flex-col bg-sidebar text-slate-300 border-r border-sidebar-border">
        <div className="px-5 h-16 flex items-center border-b border-sidebar-border">
          <Link href="/" aria-label="Udhaar Ledger home">
            <Logo size={34} tagline />
          </Link>
        </div>
        <NavList pathname={pathname} onNavigate={() => {}} />
        {profile}
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-ink-900/70 backdrop-blur-sm md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              className="fixed z-50 top-0 left-0 h-full w-72 flex flex-col bg-sidebar text-slate-300 md:hidden"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.22 }}
            >
              <div className="px-5 h-14 flex items-center justify-between border-b border-sidebar-border">
                <LogoMark size={30} />
                <button
                  onClick={() => setOpen(false)}
                  className="p-2 rounded-lg text-sidebar-muted hover:text-white"
                  aria-label="Close navigation"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <NavList pathname={pathname} onNavigate={() => setOpen(false)} />
              {profile}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

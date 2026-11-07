"use client";

import { useState } from "react";
import Link from "next/link";
import { Download, RefreshCw, Plus, ChevronRight } from "lucide-react";
import { downloadFile } from "@/lib/api";
import PaymentRecordModal from "@/components/PaymentRecordModal";
import { useMe } from "@/components/Providers";

interface NavbarProps {
  title?: string;
  subtitle?: string;
  breadcrumbs?: { label: string; href?: string }[];
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export default function Navbar({
  title = "Overview",
  subtitle,
  breadcrumbs,
  onRefresh,
  isRefreshing = false,
}: NavbarProps) {
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const { canEdit } = useMe();

  return (
    <header className="min-h-16 bg-white/85 backdrop-blur-md border-b border-border px-5 md:px-8 py-2.5 flex items-center justify-between gap-4 sticky top-14 md:top-0 z-30">
      <div className="min-w-0">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav aria-label="Breadcrumb" className="hidden sm:flex items-center gap-1 text-[11px] text-slate-400 mb-0.5">
            {breadcrumbs.map((b, i) => (
              <span key={i} className="flex items-center gap-1">
                {b.href ? (
                  <Link href={b.href} className="hover:text-slate-600 transition-colors">
                    {b.label}
                  </Link>
                ) : (
                  <span className={i === breadcrumbs.length - 1 ? "text-slate-600 font-medium" : ""}>{b.label}</span>
                )}
                {i < breadcrumbs.length - 1 && <ChevronRight className="w-3 h-3" />}
              </span>
            ))}
          </nav>
        )}
        <h1 className="text-lg font-semibold text-ink-900 tracking-tight truncate leading-tight">{title}</h1>
        {subtitle && <p className="hidden md:block text-xs text-slate-500 truncate">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-2">
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            aria-label="Refresh data"
            className="inline-flex items-center gap-1.5 h-9 px-3 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-border rounded-xl transition-colors disabled:opacity-60"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-brand-600" : "text-slate-500"}`} />
            <span className="hidden md:inline">{isRefreshing ? "Refreshing" : "Refresh"}</span>
          </button>
        )}
        <button
          onClick={() => downloadFile("/export/invoices", "receivables.csv")}
          className="hidden sm:inline-flex items-center gap-1.5 h-9 px-3 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-border rounded-xl transition-colors"
        >
          <Download className="w-3.5 h-3.5 text-slate-500" />
          Export
        </button>
        {canEdit && (
        <button
          onClick={() => setPaymentModalOpen(true)}
          className="inline-flex items-center gap-1.5 h-9 px-3.5 text-xs font-semibold text-ink-900 bg-accent-400 hover:bg-accent-300 rounded-xl shadow-subtle transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Record payment</span>
        </button>
        )}
      </div>

      <PaymentRecordModal
        isOpen={paymentModalOpen}
        onClose={() => setPaymentModalOpen(false)}
        onPaymentRecorded={() => {
          if (onRefresh) onRefresh();
        }}
      />
    </header>
  );
}

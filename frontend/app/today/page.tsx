"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Phone,
  MessageSquare,
  Gavel,
  ShieldAlert,
  Info,
  Minus,
  Plus,
  ChevronDown,
  CheckCircle2,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { PageBody, AnimatedNumber } from "@/components/ui";
import { apiFetch, formatINR } from "@/lib/api";
import { useMe } from "@/components/Providers";

type LaneKey = "call" | "escalate" | "resolve" | "message";

interface Account {
  customer_id: string;
  customer_name: string;
  customer_phone?: string | null;
  lane: LaneKey;
  overdue_amount: string;
  oldest_days_past_due: number;
  open_invoice_count: number;
  pattern: string;
  limited_history: boolean;
  reason: string;
  suggested_action: string;
  what_would_change: string;
  disputed_invoice_numbers: string[];
  disputed_invoice_ids: string[];
}

interface TodayData {
  as_of: string;
  call_slots: number;
  call: Account[];
  escalate: Account[];
  resolve: Account[];
  message: Account[];
  days_since_last_receipt: number | null;
  data_stale: boolean;
  method: string;
}

const LANES: {
  key: LaneKey;
  title: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
  chip: string;
  edge: string;
}[] = [
  { key: "call", title: "Call today", hint: "Best use of today's calls, by recoverable rupees", icon: Phone, chip: "bg-emerald-50 text-emerald-700 ring-emerald-200", edge: "bg-emerald-500" },
  { key: "escalate", title: "Escalate", hint: "Owner decides: visit, hold supply or settle", icon: ShieldAlert, chip: "bg-rose-50 text-rose-700 ring-rose-200", edge: "bg-rose-500" },
  { key: "resolve", title: "Resolve", hint: "Disputed. Not chased until cleared", icon: Gavel, chip: "bg-accent-50 text-accent-700 ring-accent-200", edge: "bg-accent-500" },
  { key: "message", title: "Message", hint: "Lower value per call. A reviewed reminder is enough", icon: MessageSquare, chip: "bg-brand-50 text-brand-700 ring-brand-200", edge: "bg-brand-400" },
];

const PATTERN_LABEL: Record<string, string> = {
  pays_when_asked: "Pays when asked",
  pays_on_its_own: "Pays on its own",
  missed_promise: "Missed a promise",
  unresponsive: "Unresponsive",
  thin_history: "Limited history",
  no_clear_pattern: "No clear pattern",
};

function AccountRow({ a, edge, onClearDispute }: { a: Account; edge: string; onClearDispute: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const { canEdit } = useMe();
  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25 }}
      className="relative"
    >
      <span className={`absolute left-0 top-3 bottom-3 w-[3px] rounded-r ${edge}`} aria-hidden />
      <div className="pl-5 pr-4 py-4 flex flex-col md:flex-row md:items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <Link href={`/customers/${a.customer_id}`} className="text-sm font-semibold text-ink-900 hover:text-brand-600">
              {a.customer_name}
            </Link>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-background text-slate-600 border border-border">
              {PATTERN_LABEL[a.pattern] ?? a.pattern}
            </span>
          </div>
          <p className="text-[13px] text-slate-700 leading-relaxed">{a.reason}</p>
          <p className="text-[13px] font-medium text-ink-900">{a.suggested_action}</p>

          <button
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-brand-600 hover:text-brand-800"
          >
            Why this lane
            <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
          <AnimatePresence initial={false}>
            {open && (
              <motion.p
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="text-xs text-slate-500 overflow-hidden"
              >
                {a.what_would_change}
              </motion.p>
            )}
          </AnimatePresence>
        </div>

        <div className="flex md:flex-col items-center md:items-end justify-between md:justify-start gap-2 flex-shrink-0">
          <span className="text-lg font-semibold font-mono tabular text-ink-900">{formatINR(a.overdue_amount)}</span>
          <span className="text-[11px] text-slate-500">
            {a.open_invoice_count} overdue · oldest {a.oldest_days_past_due}d
          </span>
          {canEdit && a.disputed_invoice_ids.map((id, i) => (
            <button
              key={id}
              onClick={() => onClearDispute(id)}
              className="text-[11px] font-semibold px-2.5 py-1.5 rounded-lg border border-border bg-white hover:bg-background"
            >
              Clear dispute {a.disputed_invoice_numbers[i]}
            </button>
          ))}
        </div>
      </div>
    </motion.li>
  );
}

export default function TodayPage() {
  const [data, setData] = useState<TodayData | null>(null);
  const [slots, setSlots] = useState(5);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await apiFetch<TodayData>(`/collections/today?call_slots=${slots}`));
    } catch (e: any) {
      setError(e.message || "Failed to load today's list");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slots]);

  const clearDispute = async (invoiceId: string) => {
    await apiFetch(`/collections/invoices/${invoiceId}/dispute`, {
      method: "POST",
      body: JSON.stringify({ disputed: false }),
    });
    load();
  };

  const total = data ? data.call.length + data.escalate.length + data.resolve.length + data.message.length : 0;

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title="Today"
        subtitle="Whom to spend today's time on, and why"
        breadcrumbs={[{ label: "Udhaar Ledger" }, { label: "Collect" }, { label: "Today" }]}
        onRefresh={load}
        isRefreshing={loading}
      />

      <PageBody>
        {data?.data_stale && (
          <div role="status" className="flex items-start gap-2.5 p-3.5 rounded-xl border border-accent-200 bg-accent-50 text-xs text-accent-700">
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>
              {data.days_since_last_receipt === null
                ? "No receipts have been entered yet."
                : `The last receipt was entered ${data.days_since_last_receipt} days ago.`}{" "}
              Paid retailers may appear overdue until receipts are up to date.
            </span>
          </div>
        )}

        {/* Summary strip */}
        <div className="surface p-4 md:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-2 flex-1">
            {LANES.map((l) => {
              const n = data?.[l.key].length ?? 0;
              return (
                <a
                  key={l.key}
                  href={`#lane-${l.key}`}
                  className={`rounded-xl px-3.5 py-3 ring-1 ring-inset transition-transform hover:-translate-y-0.5 ${l.chip}`}
                >
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold whitespace-nowrap">
                    <l.icon className="w-3.5 h-3.5 flex-shrink-0" /> {l.title}
                  </div>
                  <div className="mt-1 text-2xl font-semibold font-mono">
                    <AnimatedNumber value={n} />
                  </div>
                </a>
              );
            })}
          </div>

          <div className="flex items-center gap-3 lg:pl-5 lg:border-l border-border">
            <div>
              <p className="text-xs font-semibold text-ink-900">Calls the team can make today</p>
              <p className="text-[11px] text-slate-500">Sets the size of the Call lane</p>
            </div>
            <div className="inline-flex items-center rounded-xl border border-border bg-white">
              <button
                aria-label="Fewer calls"
                onClick={() => setSlots((s) => Math.max(1, s - 1))}
                className="w-9 h-9 flex items-center justify-center text-slate-600 hover:bg-background rounded-l-xl"
              >
                <Minus className="w-4 h-4" />
              </button>
              <span className="w-9 text-center text-sm font-semibold font-mono tabular" aria-live="polite">
                {slots}
              </span>
              <button
                aria-label="More calls"
                onClick={() => setSlots((s) => Math.min(50, s + 1))}
                className="w-9 h-9 flex items-center justify-center text-slate-600 hover:bg-background rounded-r-xl"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-start gap-2 text-xs text-slate-500 max-w-3xl">
          <Info className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
          <span>
            Accounts sit in lanes, not numbered ranks, because the order inside a lane is only stable as a tier. Weights are assumptions not yet validated on real outcomes. Nothing is sent automatically.
          </span>
        </div>

        {error && <div role="alert" className="p-3.5 rounded-xl border border-rose-200 bg-rose-50 text-xs text-rose-800">{error}</div>}

        {!loading && data && total === 0 && (
          <div className="surface py-16 text-center">
            <CheckCircle2 className="w-9 h-9 text-emerald-500 mx-auto" />
            <p className="mt-3 text-sm font-semibold text-ink-900">All clear</p>
            <p className="text-xs text-slate-500 mt-1">No overdue accounts need attention today.</p>
          </div>
        )}

        {LANES.map((lane) => {
          const items = data?.[lane.key] ?? [];
          if (data && items.length === 0 && total > 0 && lane.key !== "call") return null;
          return (
            <section id={`lane-${lane.key}`} key={lane.key} className="surface overflow-hidden scroll-mt-24">
              <header className="flex items-center justify-between gap-3 px-5 py-3.5 border-b border-border-light">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg ring-1 ring-inset text-xs font-semibold ${lane.chip}`}>
                    <lane.icon className="w-3.5 h-3.5" />
                    {lane.title}
                  </span>
                  <span className="text-xs text-slate-500">{lane.hint}</span>
                </div>
                <span className="text-xs font-semibold text-slate-600 font-mono">{items.length}</span>
              </header>
              {loading && !data ? (
                <div className="p-5 space-y-3">
                  {[0, 1].map((i) => (
                    <div key={i} className="h-16 rounded-xl bg-background animate-pulse" />
                  ))}
                </div>
              ) : items.length === 0 ? (
                <p className="px-5 py-8 text-xs text-slate-400 text-center">Nothing here today.</p>
              ) : (
                <ul className="divide-y divide-border-light">
                  <AnimatePresence initial={false}>
                    {items.map((a) => (
                      <AccountRow key={a.customer_id} a={a} edge={lane.edge} onClearDispute={clearDispute} />
                    ))}
                  </AnimatePresence>
                </ul>
              )}
            </section>
          );
        })}

        <p className="text-[11px] text-slate-400">
          Method: {data?.method}. For invoice-level reminders and promise tracking, use the{" "}
          <Link href="/queue" className="underline">invoice queue</Link>.
        </p>
      </PageBody>
    </div>
  );
}

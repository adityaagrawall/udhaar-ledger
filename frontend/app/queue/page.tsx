"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Download, MessageCircle, Handshake, Info, CheckCircle2, AlertOctagon } from "lucide-react";
import Navbar from "@/components/Navbar";
import ReminderModal from "@/components/ReminderModal";
import InvoiceModal from "@/components/InvoiceModal";
import FollowUpModal from "@/components/FollowUpModal";
import { RiskBadge } from "@/components/Badge";
import { useAnnounce, useMe } from "@/components/Providers";
import {
  PageBody,
  Toolbar,
  SearchInput,
  Select,
  Pagination,
  ErrorBanner,
  SkeletonRows,
  tbl,
} from "@/components/ui";
import { formatINR, formatDate, apiFetch, downloadFile } from "@/lib/api";

function ScorePill({ score }: { score: number }) {
  const [tone, tier] =
    score >= 80
      ? ["bg-rose-50 text-rose-700 ring-rose-200", "high"]
      : score >= 60
      ? ["bg-accent-50 text-accent-700 ring-accent-200", "medium"]
      : ["bg-brand-50 text-brand-700 ring-brand-200", "lower"];
  const pct = Math.min(100, (score / 115) * 100);
  return (
    <div className="w-16">
      <span className={`inline-flex px-2 py-0.5 rounded-md ring-1 ring-inset font-mono text-xs font-semibold ${tone}`}>
        <span className="sr-only">Priority score </span>
        {score.toFixed(0)}
        <span className="sr-only">, {tier} priority</span>
      </span>
      <div className="mt-1.5 h-1 rounded-full bg-background overflow-hidden" aria-hidden>
        <motion.div
          className="h-full bg-brand-500"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

export default function QueuePage() {
  const { canEdit } = useMe();
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const perPage = 25;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const announce = useAnnounce();

  const [riskTier, setRiskTier] = useState("");
  const [minDays, setMinDays] = useState(0);
  const [promise, setPromise] = useState("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");

  const [reminderFor, setReminderFor] = useState<any>(null);
  const [followUpFor, setFollowUpFor] = useState<any>(null);
  const [invoiceId, setInvoiceId] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      let url = `/collections/queue?page=${page}&per_page=${perPage}&min_days_overdue=${minDays}`;
      if (riskTier) url += `&risk_tier=${riskTier}`;
      if (promise) url += `&promise_filter=${promise}`;
      if (debounced.trim()) url += `&search=${encodeURIComponent(debounced.trim())}`;
      const data = await apiFetch<any>(url);
      setItems(data.items || []);
      setTotal(data.total || 0);
      announce(`${(data.total || 0).toLocaleString("en-IN")} open invoices. Showing page ${page}.`);
    } catch (err: any) {
      setError(err.message || "Failed to load the queue");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, riskTier, minDays, promise, debounced]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));
  const resetTo = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setPage(1);
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title="Invoice queue"
        subtitle="Every open invoice, with reminders and promise-to-pay tracking"
        breadcrumbs={[{ label: "Udhaar Ledger" }, { label: "Collect" }, { label: "Invoice queue" }]}
        onRefresh={load}
        isRefreshing={loading}
      />

      <PageBody>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-ink-900">
              <span className="tabular">{total.toLocaleString("en-IN")}</span> open invoices
            </h2>
            <p className="mt-1 text-sm text-slate-500 flex items-start gap-1.5 max-w-2xl">
              <Info aria-hidden className="w-4 h-4 mt-0.5 text-slate-500 flex-shrink-0" />
              <span>
                Invoice-level score: days overdue (up to 40) + amount (up to 30) + risk tier (up to 20) + broken promise (15) + no recent
                contact (10). For the account-level daily list, use{" "}
                <Link href="/today" className="font-semibold text-brand-700 underline hover:no-underline">
                  Today
                </Link>
                .
              </span>
            </p>
          </div>
          <button
            onClick={() => downloadFile("/export/queue", "collection-queue.csv")}
            className="inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-white border border-border text-xs font-semibold text-ink-900 hover:bg-background whitespace-nowrap self-start md:self-auto"
          >
            <Download aria-hidden className="w-4 h-4 text-slate-500" /> Export queue
          </button>
        </div>

        <Toolbar>
          <SearchInput value={search} onChange={setSearch} placeholder="Search customer or invoice number" />
          <div className="flex flex-wrap items-center gap-3">
            <Select
              label="Promises"
              value={promise}
              onChange={resetTo(setPromise)}
              options={[
                { value: "", label: "All" },
                { value: "broken", label: "Broken" },
                { value: "promised", label: "Active" },
              ]}
            />
            <Select
              label="Risk"
              value={riskTier}
              onChange={resetTo(setRiskTier)}
              options={[
                { value: "", label: "All tiers" },
                { value: "high", label: "High" },
                { value: "medium", label: "Medium" },
                { value: "low", label: "Low" },
              ]}
            />
            <Select
              label="Overdue"
              value={minDays}
              onChange={(v) => resetTo(setMinDays)(parseInt(v))}
              options={[
                { value: 0, label: "Any" },
                { value: 15, label: "15+ days" },
                { value: 30, label: "30+ days" },
                { value: 60, label: "60+ days" },
                { value: 90, label: "90+ days" },
              ]}
            />
          </div>
        </Toolbar>

        {error && <ErrorBanner message={error} onRetry={load} />}

        <div className="surface overflow-hidden">
          <div className="relative overflow-x-auto" role="region" aria-label="Open invoices, scrollable table" tabIndex={0}>
            <table className={tbl.table} aria-busy={loading}>
              <caption className="sr-only">Open invoices ranked by invoice-level priority score</caption>
              <thead className={tbl.thead}>
                <tr>
                  <th scope="col" className={tbl.th}>Score</th>
                  <th scope="col" className={tbl.th}>Invoice</th>
                  <th scope="col" className={tbl.th}>Customer</th>
                  <th scope="col" className={`${tbl.th} text-right`}>Outstanding</th>
                  <th scope="col" className={tbl.th}>Aging</th>
                  <th scope="col" className={tbl.th}>Main driver</th>
                  <th scope="col" className={tbl.th}>Last contact</th>
                  <th scope="col" className={`${tbl.th} text-right`}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <SkeletonRows cols={8} />
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-16 text-center">
                      <CheckCircle2 aria-hidden className="w-8 h-8 text-emerald-600 mx-auto" />
                      <p className="mt-2 text-sm font-semibold text-ink-900">Nothing matches</p>
                      <p className="text-xs text-slate-500">No open invoices match these filters.</p>
                    </td>
                  </tr>
                ) : (
                  items.map((item, i) => (
                    <motion.tr
                      key={item.invoice_id}
                      className={tbl.tr}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: Math.min(i, 12) * 0.025 }}
                    >
                      <td className={tbl.td}>
                        <ScorePill score={item.priority_score} />
                      </td>
                      <td className={tbl.td}>
                        <button
                          onClick={() => setInvoiceId(item.invoice_id)}
                          className="font-mono text-xs font-semibold text-brand-700 hover:text-brand-800 underline hover:no-underline whitespace-nowrap py-2"
                        >
                          <span className="sr-only">Open invoice </span>
                          {item.invoice_number}
                        </button>
                        {item.has_broken_promise && (
                          <span className="mt-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-rose-700">
                            <AlertOctagon aria-hidden className="w-3 h-3" /> Broken promise
                          </span>
                        )}
                      </td>
                      <td className={tbl.td}>
                        <Link
                          href={`/customers/${item.customer_id}`}
                          className="font-semibold text-ink-900 hover:text-brand-700 hover:underline inline-flex items-center min-h-11 md:min-h-0"
                        >
                          {item.customer_name}
                        </Link>
                        <div className="mt-1">
                          <RiskBadge tier={item.risk_tier} />
                        </div>
                      </td>
                      <td className={`${tbl.td} text-right font-mono font-semibold tabular text-ink-900 whitespace-nowrap`}>
                        {formatINR(item.outstanding_balance)}
                      </td>
                      <td className={tbl.td}>
                        <span
                          className={`block font-semibold whitespace-nowrap ${item.days_overdue > 0 ? "text-rose-600" : "text-slate-500"}`}
                        >
                          {item.days_overdue > 0 ? `${item.days_overdue}d overdue` : "Not yet due"}
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono whitespace-nowrap">due {formatDate(item.due_date)}</span>
                      </td>
                      <td className={`${tbl.td} text-slate-600 max-w-[220px]`}>
                        <span className="line-clamp-2 text-xs">{item.priority_reasons?.[0] || "Past credit terms"}</span>
                      </td>
                      <td className={`${tbl.td} text-xs text-slate-500 whitespace-nowrap`}>
                        {item.last_follow_up_date ? formatDate(item.last_follow_up_date) : <span className="italic text-slate-400">None</span>}
                      </td>
                      <td className={`${tbl.td} text-right`}>
                        <div className="flex items-center justify-end gap-1.5">
                          {canEdit && (
                            <button
                              onClick={() =>
                                setFollowUpFor({
                                  id: item.invoice_id,
                                  invoice_number: item.invoice_number,
                                  customer_id: item.customer_id,
                                  customer_name: item.customer_name,
                                  outstanding_balance: item.outstanding_balance,
                                })
                              }
                              className="inline-flex items-center gap-1 h-8 px-2.5 rounded-lg bg-background hover:bg-brand-50 text-xs font-semibold text-ink-900 border border-border"
                            >
                              <Handshake aria-hidden className="w-3.5 h-3.5" /> Log
                              <span className="sr-only"> a call or promise to pay for {item.customer_name}, invoice {item.invoice_number}</span>
                            </button>
                          )}
                          <button
                            onClick={() =>
                              setReminderFor({
                                id: item.invoice_id,
                                invoice_number: item.invoice_number,
                                customer_id: item.customer_id,
                                customer_name: item.customer_name,
                                customer_phone: item.customer_phone,
                                outstanding_balance: item.outstanding_balance,
                                due_date: item.due_date,
                                days_overdue: item.days_overdue,
                                open_follow_up_id: item.open_follow_up_id,
                              })
                            }
                            className="inline-flex items-center gap-1 h-8 px-2.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-xs font-semibold text-emerald-800 ring-1 ring-inset ring-emerald-200"
                          >
                            <MessageCircle aria-hidden className="w-3.5 h-3.5" /> Remind
                            <span className="sr-only"> {item.customer_name}, invoice {item.invoice_number}, draft for review</span>
                          </button>
                        </div>
                      </td>
                    </motion.tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={totalPages} total={total} noun="invoices" onPage={setPage} disabled={loading} />
        </div>
      </PageBody>

      <ReminderModal isOpen={!!reminderFor} onClose={() => setReminderFor(null)} invoice={reminderFor} onFollowUpUpdated={load} />
      <InvoiceModal
        isOpen={!!invoiceId}
        onClose={() => setInvoiceId(null)}
        invoiceId={invoiceId}
        onDraftReminder={(inv) => setReminderFor(inv)}
      />
      <FollowUpModal isOpen={!!followUpFor} onClose={() => setFollowUpFor(null)} invoice={followUpFor} onFollowUpCreated={load} />
    </div>
  );
}

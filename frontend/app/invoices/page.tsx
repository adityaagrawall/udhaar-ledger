"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Download, MessageCircle, ChevronRight, FileSearch } from "lucide-react";
import Navbar from "@/components/Navbar";
import InvoiceModal from "@/components/InvoiceModal";
import ReminderModal from "@/components/ReminderModal";
import { StatusBadge } from "@/components/Badge";
import { PageBody, Toolbar, SearchInput, Segmented, Pagination, ErrorBanner, SkeletonRows, tbl } from "@/components/ui";
import { formatINR, formatDate, apiFetch, downloadFile } from "@/lib/api";

type StatusKey = "" | "overdue" | "partial" | "sent" | "paid";

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const perPage = 25;
  const [status, setStatus] = useState<StatusKey>("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [reminderFor, setReminderFor] = useState<any>(null);

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
      let url = `/invoices?page=${page}&per_page=${perPage}`;
      if (status) url += `&status=${status}`;
      if (debounced.trim()) url += `&search=${encodeURIComponent(debounced.trim())}`;
      const data = await apiFetch<any>(url);
      setInvoices(data.items || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err.message || "Failed to load invoices");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, status, debounced]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title="Receivables ledger"
        subtitle="Every invoice with its payment allocations and live balance"
        breadcrumbs={[{ label: "Udhaar Ledger" }, { label: "Books" }, { label: "Receivables ledger" }]}
        onRefresh={load}
        isRefreshing={loading}
      />

      <PageBody>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-ink-900">
              <span className="tabular">{total.toLocaleString("en-IN")}</span> invoices
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Balance is always invoice total minus allocated payments, never a joined sum.
            </p>
          </div>
          <button
            onClick={() => downloadFile("/export/invoices", "receivables.csv")}
            className="inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-white border border-border text-xs font-semibold text-ink-900 hover:bg-background"
          >
            <Download className="w-4 h-4 text-slate-500" /> Export CSV
          </button>
        </div>

        <Toolbar>
          <SearchInput value={search} onChange={setSearch} placeholder="Search customer or invoice number" />
          <Segmented<StatusKey>
            label="status"
            value={status}
            onChange={(v) => {
              setStatus(v);
              setPage(1);
            }}
            options={[
              { value: "", label: "All" },
              { value: "overdue", label: "Overdue" },
              { value: "partial", label: "Partial" },
              { value: "sent", label: "Open" },
              { value: "paid", label: "Paid" },
            ]}
          />
        </Toolbar>

        {error && <ErrorBanner message={error} onRetry={load} />}

        <div className="surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className={tbl.table}>
              <thead className={tbl.thead}>
                <tr>
                  <th scope="col" className={tbl.th}>Invoice</th>
                  <th scope="col" className={tbl.th}>Customer</th>
                  <th scope="col" className={tbl.th}>Issued</th>
                  <th scope="col" className={tbl.th}>Due</th>
                  <th scope="col" className={`${tbl.th} text-right`}>Total</th>
                  <th scope="col" className={`${tbl.th} text-right`}>Balance</th>
                  <th scope="col" className={tbl.th}>Status</th>
                  <th scope="col" className={`${tbl.th} text-right`}></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <SkeletonRows cols={8} />
                ) : invoices.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-16 text-center">
                      <FileSearch className="w-8 h-8 text-slate-300 mx-auto" />
                      <p className="mt-2 text-sm font-semibold text-ink-900">No invoices found</p>
                      <p className="text-xs text-slate-500">Try a different search or status.</p>
                    </td>
                  </tr>
                ) : (
                  invoices.map((inv, i) => {
                    const paidPct =
                      Number(inv.total_amount) > 0
                        ? Math.max(0, Math.min(100, (1 - Number(inv.outstanding_balance) / Number(inv.total_amount)) * 100))
                        : 0;
                    return (
                      <motion.tr
                        key={inv.id}
                        onClick={() => setInvoiceId(inv.id)}
                        className={`${tbl.tr} cursor-pointer group`}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(i, 12) * 0.025 }}
                      >
                        <td className={`${tbl.td} font-mono text-xs font-semibold text-brand-600 whitespace-nowrap`}>{inv.invoice_number}</td>
                        <td className={tbl.td} onClick={(e) => e.stopPropagation()}>
                          <Link href={`/customers/${inv.customer_id}`} className="font-semibold text-ink-900 hover:text-brand-600">
                            {inv.customer_name}
                          </Link>
                        </td>
                        <td className={`${tbl.td} text-xs text-slate-500 whitespace-nowrap`}>{formatDate(inv.issue_date)}</td>
                        <td className={`${tbl.td} text-xs whitespace-nowrap`}>
                          <span className="text-slate-600">{formatDate(inv.due_date)}</span>
                          {inv.days_overdue > 0 && inv.status !== "paid" && (
                            <span className="block text-[11px] font-semibold text-rose-600">{inv.days_overdue}d overdue</span>
                          )}
                        </td>
                        <td className={`${tbl.td} text-right font-mono tabular text-slate-600`}>{formatINR(inv.total_amount)}</td>
                        <td className={`${tbl.td} text-right`}>
                          <span className="font-mono font-semibold tabular text-ink-900">{formatINR(inv.outstanding_balance)}</span>
                          <div className="mt-1.5 ml-auto w-20 h-1 rounded-full bg-background overflow-hidden" title={`${paidPct.toFixed(0)}% paid`}>
                            <div className="h-full bg-emerald-500" style={{ width: `${paidPct}%` }} />
                          </div>
                        </td>
                        <td className={tbl.td}>
                          <StatusBadge status={inv.status} />
                        </td>
                        <td className={`${tbl.td} text-right`} onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-1.5">
                            {inv.status !== "paid" && (
                              <button
                                onClick={() =>
                                  setReminderFor({
                                    id: inv.id,
                                    invoice_number: inv.invoice_number,
                                    customer_name: inv.customer_name,
                                    outstanding_balance: inv.outstanding_balance,
                                    due_date: inv.due_date,
                                    days_overdue: inv.days_overdue,
                                  })
                                }
                                aria-label={`Draft reminder for ${inv.invoice_number}`}
                                className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-emerald-700 hover:bg-emerald-50"
                              >
                                <MessageCircle className="w-4 h-4" />
                              </button>
                            )}
                            <button
                              onClick={() => setInvoiceId(inv.id)}
                              aria-label={`Open ${inv.invoice_number}`}
                              className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-400 group-hover:text-brand-600 hover:bg-brand-50"
                            >
                              <ChevronRight className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </motion.tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={totalPages} total={total} noun="invoices" onPage={setPage} disabled={loading} />
        </div>
      </PageBody>

      <InvoiceModal
        isOpen={!!invoiceId}
        onClose={() => setInvoiceId(null)}
        invoiceId={invoiceId}
        onDraftReminder={(inv) => setReminderFor(inv)}
      />
      <ReminderModal isOpen={!!reminderFor} onClose={() => setReminderFor(null)} invoice={reminderFor} onFollowUpUpdated={load} />
    </div>
  );
}

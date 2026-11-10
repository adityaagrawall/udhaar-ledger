"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Plus,
  MessageCircle,
  Handshake,
  Phone,
  Mail,
  MapPin,
  FileText,
  AlertCircle,
  Wallet,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import PaymentRecordModal from "@/components/PaymentRecordModal";
import ReminderModal from "@/components/ReminderModal";
import FollowUpModal from "@/components/FollowUpModal";
import Badge, { RiskBadge } from "@/components/Badge";
import { useMe } from "@/components/Providers";
import { PageBody, Card, SectionTitle, Segmented, AnimatedNumber, stagger, rise, tbl } from "@/components/ui";
import { formatINR, formatINRCompact, formatDate, apiFetch } from "@/lib/api";

type Tab = "ledger" | "invoices" | "promises";

const HEALTH: Record<string, { variant: "success" | "warning" | "danger" | "brand"; label: string }> = {
  HEALTHY: { variant: "success", label: "Healthy" },
  MONITOR: { variant: "brand", label: "Monitor" },
  WARNING: { variant: "warning", label: "Warning" },
  CRITICAL: { variant: "danger", label: "Critical" },
};

const AGING = [
  { key: "current", label: "Not due", color: "bg-emerald-500" },
  { key: "days_1_30", label: "1–30d", color: "bg-brand-500" },
  { key: "days_31_60", label: "31–60d", color: "bg-brand-300" },
  { key: "days_61_90", label: "61–90d", color: "bg-accent-500" },
  { key: "beyond_90", label: "90d+", color: "bg-rose-500" },
] as const;

function CreditRing({ pct }: { pct: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const shown = Math.min(100, pct);
  const stroke = pct > 100 ? "#E11D48" : pct > 75 ? "#F59E0B" : "#10B981";
  return (
    <div className="relative w-36 h-36">
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90" aria-hidden>
        <circle cx="60" cy="60" r={r} fill="none" stroke="#EEF1F8" strokeWidth="10" />
        <motion.circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={stroke}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - (shown / 100) * c }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold font-mono text-ink-900">
          <AnimatedNumber value={pct} format={(n) => `${n.toFixed(0)}%`} />
        </span>
        <span className="text-[10px] uppercase tracking-[0.12em] text-slate-500">credit used</span>
      </div>
    </div>
  );
}

export default function CustomerDetailPage() {
  const params = useParams();
  const customerId = params?.id as string;
  const { canEdit } = useMe();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("invoices");

  const [payOpen, setPayOpen] = useState(false);
  const [payInvoice, setPayInvoice] = useState<string | undefined>();
  const [reminderFor, setReminderFor] = useState<any>(null);
  const [followUpFor, setFollowUpFor] = useState<any>(null);

  const load = async () => {
    if (!customerId) return;
    setLoading(true);
    setError(null);
    try {
      setData(await apiFetch<any>(`/customers/${customerId}/ledger`));
    } catch (err: any) {
      setError(err.message || "Failed to load customer");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId]);

  if (loading && !data) {
    return (
      <div className="flex-1 flex flex-col min-h-screen">
        <Navbar title="Customer" breadcrumbs={[{ label: "Customers", href: "/customers" }, { label: "Loading" }]} />
        <PageBody>
          <div className="h-40 surface animate-pulse" />
          <div className="grid md:grid-cols-3 gap-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-28 surface animate-pulse" />
            ))}
          </div>
        </PageBody>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex-1 flex flex-col min-h-screen">
        <Navbar title="Customer" breadcrumbs={[{ label: "Customers", href: "/customers" }, { label: "Not found" }]} />
        <PageBody className="max-w-xl text-center py-20">
          <AlertCircle className="w-10 h-10 text-rose-500 mx-auto" />
          <h2 className="mt-3 text-base font-semibold text-ink-900">Customer not found</h2>
          <p className="text-sm text-slate-500 mt-1">{error}</p>
          <Link href="/customers" className="mt-5 inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-ink-900 text-white text-xs font-semibold">
            <ArrowLeft className="w-4 h-4" /> Back to customers
          </Link>
        </PageBody>
      </div>
    );
  }

  const { customer, credit_summary: credit, aging_summary: aging, ledger, open_invoices: openInvs, promises } = data;
  const health = HEALTH[credit.health_status] ?? HEALTH.MONITOR;
  const agingTotal = AGING.reduce((s, a) => s + Number(aging[a.key] || 0), 0);

  const reminderPayload = (inv: any) => ({
    id: inv.id,
    invoice_number: inv.invoice_number,
    customer_name: customer.name,
    customer_phone: customer.phone,
    outstanding_balance: inv.outstanding_balance,
    due_date: inv.due_date,
    days_overdue: inv.days_overdue,
  });

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title={customer.name}
        subtitle="Credit position, statement of account and promises"
        breadcrumbs={[{ label: "Udhaar Ledger" }, { label: "Customers", href: "/customers" }, { label: customer.name }]}
        onRefresh={load}
        isRefreshing={loading}
      />

      <PageBody>
        <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
          {/* Header */}
          <motion.div variants={rise} className="surface overflow-hidden">
            <div className="h-20 bg-hero-ink relative">
              <div className="absolute inset-0 bg-ledger-grid [background-size:28px_28px] opacity-50" aria-hidden />
            </div>
            <div className="px-6 pb-6 flex flex-col xl:flex-row xl:items-end justify-between gap-5">
              <div className="flex flex-col sm:flex-row sm:items-end gap-4">
                <span className="-mt-8 w-16 h-16 flex-shrink-0 rounded-2xl bg-white ring-4 ring-white shadow-elevated flex items-center justify-center text-xl font-bold text-brand-700">
                  {customer.name
                    .split(/\s+/)
                    .map((p: string) => p[0])
                    .slice(0, 2)
                    .join("")}
                </span>
                <div className="pt-3 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-xl font-semibold text-ink-900 tracking-tight">{customer.name}</h2>
                    <RiskBadge tier={customer.risk_tier} />
                    <Badge variant={health.variant} size="sm" dot>
                      {health.label}
                    </Badge>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                    {customer.gst_number && <span className="font-mono">GSTIN {customer.gst_number}</span>}
                    {customer.phone && (
                      <span className="inline-flex items-center gap-1">
                        <Phone className="w-3 h-3" /> {customer.phone}
                      </span>
                    )}
                    {customer.email && (
                      <span className="inline-flex items-center gap-1">
                        <Mail className="w-3 h-3" /> {customer.email}
                      </span>
                    )}
                    {customer.address && (
                      <span className="inline-flex items-center gap-1 max-w-xs truncate">
                        <MapPin className="w-3 h-3" /> {customer.address}
                      </span>
                    )}
                    <span>Terms: {customer.payment_terms_days} days</span>
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {canEdit && (
                  <button
                    onClick={() => {
                      setPayInvoice(undefined);
                      setPayOpen(true);
                    }}
                    className="inline-flex items-center gap-1.5 h-10 px-4 rounded-xl bg-accent-400 hover:bg-accent-300 text-ink-900 text-xs font-semibold"
                  >
                    <Plus className="w-4 h-4" /> Record payment
                  </button>
                )}
                {openInvs.length > 0 && (
                  <button
                    onClick={() => setReminderFor(reminderPayload(openInvs[0]))}
                    className="inline-flex items-center gap-1.5 h-10 px-4 rounded-xl bg-white border border-border hover:bg-background text-xs font-semibold text-ink-900"
                  >
                    <MessageCircle className="w-4 h-4 text-emerald-600" /> Draft reminder
                  </button>
                )}
              </div>
            </div>
          </motion.div>

          {/* Credit + aging */}
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_1.4fr] gap-5">
            <motion.div variants={rise}>
              <Card className="h-full flex flex-col sm:flex-row items-center gap-6">
                <CreditRing pct={Number(credit.utilization_pct)} />
                <dl className="flex-1 w-full grid grid-cols-2 gap-x-6 gap-y-3 text-xs">
                  {[
                    ["Credit limit", formatINR(credit.credit_limit)],
                    ["Available", formatINR(credit.available_credit)],
                    ["Outstanding", formatINR(credit.total_outstanding)],
                    ["Overdue", formatINR(credit.total_overdue)],
                    ["Lifetime billed", formatINR(credit.lifetime_invoiced)],
                    ["Lifetime collected", formatINR(credit.lifetime_collected)],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-slate-500">{k}</dt>
                      <dd
                        className={`mt-0.5 font-mono font-semibold tabular ${
                          k === "Overdue" && Number(credit.total_overdue) > 0 ? "text-rose-600" : "text-ink-900"
                        }`}
                      >
                        {v}
                      </dd>
                    </div>
                  ))}
                </dl>
              </Card>
            </motion.div>

            <motion.div variants={rise}>
              <Card className="h-full">
                <SectionTitle
                  title="Aging of this account"
                  hint={`${credit.overdue_invoices_count} overdue invoice${credit.overdue_invoices_count === 1 ? "" : "s"}`}
                />
                <div className="flex h-3 rounded-full overflow-hidden bg-background">
                  {AGING.map((a, i) => {
                    const v = Number(aging[a.key] || 0);
                    if (!agingTotal || !v) return null;
                    return (
                      <motion.div
                        key={a.key}
                        className={a.color}
                        initial={{ width: 0 }}
                        animate={{ width: `${(v / agingTotal) * 100}%` }}
                        transition={{ duration: 0.6, delay: 0.1 * i }}
                        title={`${a.label}: ${formatINR(v)}`}
                      />
                    );
                  })}
                </div>
                <div className="mt-4 grid grid-cols-5 gap-2">
                  {AGING.map((a) => (
                    <div key={a.key} className="rounded-xl bg-background px-2.5 py-2">
                      <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
                        <span className={`w-1.5 h-1.5 rounded-full ${a.color}`} /> {a.label}
                      </div>
                      <div className="mt-1 text-xs font-mono font-semibold text-ink-900 tabular truncate" title={formatINR(aging[a.key])}>
                        {formatINRCompact(aging[a.key])}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </motion.div>
          </div>

          {/* Tabs */}
          <motion.div variants={rise} className="surface overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border-light flex flex-wrap items-center justify-between gap-3">
              <Segmented<Tab>
                label="customer-tab"
                value={tab}
                onChange={setTab}
                options={[
                  { value: "invoices", label: `Open invoices (${openInvs.length})` },
                  { value: "ledger", label: `Statement (${ledger.length})` },
                  { value: "promises", label: `Promises (${promises.length})` },
                ]}
              />
            </div>

            <div className="overflow-x-auto">
              {tab === "invoices" && (
                <table className={tbl.table}>
                  <thead className={tbl.thead}>
                    <tr>
                      <th scope="col" className={tbl.th}>Invoice</th>
                      <th scope="col" className={tbl.th}>Due</th>
                      <th scope="col" className={`${tbl.th} text-right`}>Total</th>
                      <th scope="col" className={`${tbl.th} text-right`}>Paid</th>
                      <th scope="col" className={`${tbl.th} text-right`}>Balance</th>
                      <th scope="col" className={`${tbl.th} text-right`}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {openInvs.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-sm text-slate-500">
                          No open invoices. This account is fully paid.
                        </td>
                      </tr>
                    ) : (
                      openInvs.map((inv: any) => (
                        <tr key={inv.id} className={tbl.tr}>
                          <td className={`${tbl.td} font-mono text-xs font-semibold text-ink-900 whitespace-nowrap`}>{inv.invoice_number}</td>
                          <td className={`${tbl.td} text-xs`}>
                            <span className="text-slate-600">{formatDate(inv.due_date)}</span>
                            {inv.days_overdue > 0 ? (
                              <span className="block text-[11px] font-semibold text-rose-600">{inv.days_overdue}d overdue</span>
                            ) : (
                              <span className="block text-[11px] text-emerald-600">Not yet due</span>
                            )}
                          </td>
                          <td className={`${tbl.td} text-right font-mono tabular text-slate-600`}>{formatINR(inv.total_amount)}</td>
                          <td className={`${tbl.td} text-right font-mono tabular text-emerald-700`}>{formatINR(inv.paid_amount)}</td>
                          <td className={`${tbl.td} text-right font-mono font-semibold tabular text-ink-900`}>
                            {formatINR(inv.outstanding_balance)}
                          </td>
                          <td className={`${tbl.td} text-right`}>
                            <div className="flex items-center justify-end gap-1.5">
                              {canEdit && (
                                <>
                                  <button
                                    onClick={() => {
                                      setPayInvoice(inv.id);
                                      setPayOpen(true);
                                    }}
                                    className="inline-flex items-center gap-1 h-8 px-2.5 rounded-lg bg-brand-50 hover:bg-brand-100 text-xs font-semibold text-brand-700"
                                  >
                                    <Wallet className="w-3.5 h-3.5" /> Allocate
                                  </button>
                                  <button
                                    onClick={() =>
                                      setFollowUpFor({
                                        id: inv.id,
                                        invoice_number: inv.invoice_number,
                                        customer_id: customer.id,
                                        customer_name: customer.name,
                                        outstanding_balance: inv.outstanding_balance,
                                      })
                                    }
                                    className="inline-flex items-center gap-1 h-8 px-2.5 rounded-lg bg-background hover:bg-brand-50 border border-border text-xs font-semibold text-ink-900"
                                  >
                                    <Handshake className="w-3.5 h-3.5" /> Log
                                  </button>
                                </>
                              )}
                              <button
                                onClick={() => setReminderFor(reminderPayload(inv))}
                                aria-label={`Draft reminder for ${inv.invoice_number}`}
                                className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-emerald-700 hover:bg-emerald-50"
                              >
                                <MessageCircle className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}

              {tab === "ledger" && (
                <table className={tbl.table}>
                  <thead className={tbl.thead}>
                    <tr>
                      <th scope="col" className={tbl.th}>Date</th>
                      <th scope="col" className={tbl.th}>Entry</th>
                      <th scope="col" className={`${tbl.th} text-right`}>Debit</th>
                      <th scope="col" className={`${tbl.th} text-right`}>Credit</th>
                      <th scope="col" className={`${tbl.th} text-right`}>Running balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-sm text-slate-500">
                          No entries yet.
                        </td>
                      </tr>
                    ) : (
                      ledger.map((e: any) => (
                        <tr key={`${e.entry_type}-${e.id}`} className={tbl.tr}>
                          <td className={`${tbl.td} text-xs text-slate-500 whitespace-nowrap`}>{formatDate(e.date)}</td>
                          <td className={tbl.td}>
                            <span className="flex items-center gap-2">
                              <span
                                className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                                  e.entry_type === "INVOICE" ? "bg-brand-50 text-brand-600" : "bg-emerald-50 text-emerald-600"
                                }`}
                              >
                                {e.entry_type === "INVOICE" ? <FileText className="w-3.5 h-3.5" /> : <Wallet className="w-3.5 h-3.5" />}
                              </span>
                              <span>
                                <span className="block text-xs font-semibold text-ink-900">{e.reference}</span>
                                <span className="block text-[10px] uppercase tracking-wide text-slate-400">{e.status}</span>
                              </span>
                            </span>
                          </td>
                          <td className={`${tbl.td} text-right font-mono tabular text-ink-900`}>{e.debit ? formatINR(e.debit) : ""}</td>
                          <td className={`${tbl.td} text-right font-mono tabular text-emerald-700`}>{e.credit ? formatINR(e.credit) : ""}</td>
                          <td className={`${tbl.td} text-right font-mono font-semibold tabular text-ink-900`}>
                            {formatINR(e.running_balance)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}

              {tab === "promises" && (
                <table className={tbl.table}>
                  <thead className={tbl.thead}>
                    <tr>
                      <th scope="col" className={tbl.th}>Invoice</th>
                      <th scope="col" className={tbl.th}>Promised for</th>
                      <th scope="col" className={`${tbl.th} text-right`}>Amount</th>
                      <th scope="col" className={tbl.th}>Status</th>
                      <th scope="col" className={tbl.th}>Channel</th>
                      <th scope="col" className={tbl.th}>Notes</th>
                      <th scope="col" className={tbl.th}>Logged</th>
                    </tr>
                  </thead>
                  <tbody>
                    {promises.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-sm text-slate-500">
                          No promises logged for this customer yet.
                        </td>
                      </tr>
                    ) : (
                      promises.map((p: any) => (
                        <tr key={p.id} className={tbl.tr}>
                          <td className={`${tbl.td} font-mono text-xs font-semibold text-ink-900`}>{p.invoice_number}</td>
                          <td className={`${tbl.td} text-xs`}>{p.promised_date ? formatDate(p.promised_date) : "—"}</td>
                          <td className={`${tbl.td} text-right font-mono tabular`}>{p.promised_amount ? formatINR(p.promised_amount) : "—"}</td>
                          <td className={tbl.td}>
                            <Badge
                              size="sm"
                              dot
                              variant={
                                p.promise_status === "broken"
                                  ? "danger"
                                  : p.promise_status === "fulfilled"
                                  ? "success"
                                  : "warning"
                              }
                            >
                              {(p.promise_status || "pending").replace("_", " ")}
                            </Badge>
                          </td>
                          <td className={`${tbl.td} text-[11px] uppercase text-slate-500`}>{p.channel}</td>
                          <td className={`${tbl.td} text-xs text-slate-600 max-w-xs`}>
                            <span className="line-clamp-2">{p.notes || "—"}</span>
                          </td>
                          <td className={`${tbl.td} text-xs text-slate-400 whitespace-nowrap`}>{formatDate(p.created_at)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}
            </div>
          </motion.div>
        </motion.div>
      </PageBody>

      <PaymentRecordModal
        isOpen={payOpen}
        onClose={() => setPayOpen(false)}
        initialCustomerId={customerId}
        initialInvoiceId={payInvoice}
        onPaymentRecorded={load}
      />
      <ReminderModal isOpen={!!reminderFor} onClose={() => setReminderFor(null)} invoice={reminderFor} onFollowUpUpdated={load} />
      <FollowUpModal isOpen={!!followUpFor} onClose={() => setFollowUpFor(null)} invoice={followUpFor} onFollowUpCreated={load} />
    </div>
  );
}

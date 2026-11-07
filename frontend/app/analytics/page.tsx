"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Timer,
  Gauge,
  PieChart,
  AlertTriangle,
  CalendarRange,
  Handshake,
  FlaskConical,
  Play,
  Info,
} from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import Navbar from "@/components/Navbar";
import { RiskBadge } from "@/components/Badge";
import Badge from "@/components/Badge";
import { useMe } from "@/components/Providers";
import { PageBody, Card, SectionTitle, StatCard, ErrorBanner, stagger, rise } from "@/components/ui";
import { formatINR, formatINRCompact, apiFetch } from "@/lib/api";

const FEATURE_LABEL: Record<string, string> = {
  late_payment_rate: "Share of past invoices paid late",
  avg_days_late: "Average days late in the past",
  customer_risk_tier_encoded: "Customer risk tier",
  total_amount: "Invoice amount",
  log_amount: "Invoice amount (log)",
  issue_to_due_days: "Credit period on invoice",
  credit_limit: "Credit limit",
  credit_utilization: "Invoice vs credit limit",
  payment_terms_days: "Agreed payment terms",
  total_historical_invoices: "Number of settled invoices",
};

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-ink-900 text-white rounded-xl px-3 py-2 text-xs shadow-dropdown space-y-1">
      <p className="font-semibold">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-brand-100">
            <span className="w-2 h-2 rounded-full" style={{ background: p.color }} /> {p.name}
          </span>
          <span className="font-mono">{formatINR(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

function ModelPanel() {
  const { canEdit } = useMe();
  const [ev, setEv] = useState<any>(null);
  const [training, setTraining] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = () =>
    apiFetch<any>("/ml/evaluation")
      .then(setEv)
      .catch((e) => setErr(e.message));

  useEffect(() => {
    load();
  }, []);

  const train = async () => {
    setTraining(true);
    setErr(null);
    try {
      await apiFetch("/ml/train", { method: "POST" });
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setTraining(false);
    }
  };

  const m = ev?.metrics || {};
  const trained = ev && !ev.is_demo && m.mae_days !== undefined;
  const imp: any[] = (ev?.feature_importance || []).slice(0, 6);
  const maxImp = Math.max(...imp.map((f) => f.importance), 0.0001);

  return (
    <Card>
      <SectionTitle
        title="Payment-delay model"
        hint="Predicts how late an invoice will be paid. A supporting signal only; Today's list uses transparent rules."
        right={
          <Badge size="sm" variant="warning" dot>
            Experimental
          </Badge>
        }
      />
      {err && <ErrorBanner message={err} />}
      {!ev ? (
        <div className="h-40 rounded-xl bg-background animate-pulse" />
      ) : !trained ? (
        <div className="rounded-xl bg-background ring-1 ring-border p-6 text-center">
          <FlaskConical className="w-7 h-7 text-slate-400 mx-auto" />
          <p className="mt-2 text-sm font-semibold text-ink-900">No model trained for this organisation yet</p>
          <p className="mt-1 text-xs text-slate-500">
            Training uses settled invoices with point-in-time features and a chronological 80/20 split.
          </p>
          {canEdit && (
            <button
              onClick={train}
              disabled={training}
              className="mt-4 inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-brand-700 hover:bg-brand-600 text-white text-xs font-semibold disabled:opacity-60"
            >
              <Play className="w-3.5 h-3.5" /> {training ? "Training…" : "Train on settled invoices"}
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="rounded-xl bg-background ring-1 ring-border p-4">
              <p className="text-[11px] uppercase tracking-[0.1em] text-slate-500">Average error on held-out invoices</p>
              <div className="mt-2 flex items-end gap-4">
                <div>
                  <p className="text-3xl font-semibold font-mono text-ink-900">{m.mae_days}d</p>
                  <p className="text-[11px] text-slate-500">model</p>
                </div>
                <div className="pb-1">
                  <p className="text-lg font-semibold font-mono text-slate-400 line-through decoration-slate-300">{m.baseline_mae_days}d</p>
                  <p className="text-[11px] text-slate-500">guess the average</p>
                </div>
                <span className="ml-auto pb-1 text-sm font-semibold text-emerald-700">−{m.error_reduction_pct}%</span>
              </div>
            </div>
            <dl className="grid grid-cols-3 gap-3 text-xs">
              {[
                ["ROC-AUC", m.roc_auc?.toFixed?.(2) ?? m.roc_auc],
                ["Accuracy", m.accuracy !== undefined ? `${(m.accuracy * (m.accuracy <= 1 ? 100 : 1)).toFixed(0)}%` : "—"],
                ["Test invoices", m.test_samples],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl ring-1 ring-border p-3">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="mt-1 font-mono font-semibold text-ink-900">{v ?? "—"}</dd>
                </div>
              ))}
            </dl>
            <p className="text-[11px] text-slate-500 flex items-start gap-1.5">
              <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
              Measured on the newest 20% of settled invoices. On this synthetic dataset the signal is modest; treat predictions as hints.
            </p>
            {canEdit && (
              <button
                onClick={train}
                disabled={training}
                className="inline-flex items-center gap-2 h-9 px-3 rounded-xl border border-border bg-white hover:bg-background text-xs font-semibold disabled:opacity-60"
              >
                <Play className="w-3.5 h-3.5" /> {training ? "Retraining…" : "Retrain"}
              </button>
            )}
          </div>
          <div>
            <p className="text-xs font-semibold text-ink-900 mb-3">What drives the prediction</p>
            <ul className="space-y-3">
              {imp.map((f, i) => (
                <li key={f.feature}>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-700">{FEATURE_LABEL[f.feature] ?? f.feature}</span>
                    <span className="font-mono text-slate-500">{(f.importance * 100).toFixed(1)}%</span>
                  </div>
                  <div className="mt-1.5 h-2 rounded-full bg-background overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-300"
                      initial={{ width: 0 }}
                      animate={{ width: `${(f.importance / maxImp) * 100}%` }}
                      transition={{ duration: 0.6, delay: i * 0.06 }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Card>
  );
}

export default function AnalyticsPage() {
  const [kpis, setKpis] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [k, t] = await Promise.all([apiFetch<any>("/analytics/distributor-kpis"), apiFetch<any[]>("/analytics/trends?months=12")]);
      setKpis(k);
      setTrends(t);
    } catch (e: any) {
      setError(e.message || "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const chartData = trends.map((t) => ({
    month: t.month,
    Invoiced: Number(t.invoiced),
    Collected: Number(t.collected),
    "Net (billed − collected)": Number(t.outstanding),
  }));
  const ptp = kpis?.ptp_stats;

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title="Analytics"
        subtitle="How fast cash comes back, where it is stuck, and what the model sees"
        breadcrumbs={[{ label: "Udhaar Ledger" }, { label: "Insights" }, { label: "Analytics" }]}
        onRefresh={load}
        isRefreshing={loading}
      />

      <PageBody>
        {error && <ErrorBanner message={error} onRetry={load} />}

        {loading && !kpis ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-32 surface animate-pulse" />
            ))}
          </div>
        ) : kpis ? (
          <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <StatCard
                label="Days sales outstanding"
                value={kpis.dso_days}
                format={(n) => `${n.toFixed(1)} d`}
                icon={Timer}
                tone="brand"
                foot={<span title={kpis.dso_formula}>Status: {kpis.dso_status}</span>}
              />
              <StatCard
                label="Collection effectiveness"
                value={kpis.collection_effectiveness_index}
                format={(n) => `${n.toFixed(1)}%`}
                icon={Gauge}
                tone="success"
                foot={<span title={kpis.cei_formula}>Share of collectible balance actually collected</span>}
              />
              <StatCard
                label="Overdue share"
                value={kpis.overdue_percentage}
                format={(n) => `${n.toFixed(1)}%`}
                icon={AlertTriangle}
                tone="danger"
                foot={`${kpis.overdue_retailers_count} of ${kpis.active_retailers_count} retailers overdue`}
              />
              <StatCard
                label="Top-5 concentration"
                value={kpis.top_5_debtor_concentration_pct}
                format={(n) => `${n.toFixed(1)}%`}
                icon={PieChart}
                tone="accent"
                foot="Of receivables held by five customers"
              />
            </div>

            <motion.div variants={rise} className="grid grid-cols-1 xl:grid-cols-[1.7fr_1fr] gap-5">
              <Card>
                <SectionTitle title="Billed vs collected" hint="Last 12 months. The line is the month's net: below zero means more was collected than billed." />
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="outGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#F59E0B" stopOpacity={0.25} />
                          <stop offset="100%" stopColor="#F59E0B" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF1F8" />
                      <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#64748B" }} axisLine={false} tickLine={false} />
                      <YAxis tickFormatter={(v) => formatINRCompact(v)} tick={{ fontSize: 11, fill: "#64748B" }} axisLine={false} tickLine={false} width={70} />
                      <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(59,92,219,0.05)" }} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="Invoiced" fill="#3B5CDB" radius={[4, 4, 0, 0]} maxBarSize={18} />
                      <Bar dataKey="Collected" fill="#10B981" radius={[4, 4, 0, 0]} maxBarSize={18} />
                      <Area dataKey="Net (billed − collected)" type="monotone" stroke="#F59E0B" strokeWidth={2} fill="url(#outGrad)" />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </Card>

              <div className="space-y-5">
                <Card>
                  <SectionTitle title="Expected inflows" hint="Open invoices falling due" right={<CalendarRange className="w-4 h-4 text-slate-400" />} />
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      ["7 days", kpis.projected_inflows.next_7_days],
                      ["15 days", kpis.projected_inflows.next_15_days],
                      ["30 days", kpis.projected_inflows.next_30_days],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded-xl bg-background px-3 py-2.5">
                        <p className="text-[11px] text-slate-500">Next {k}</p>
                        <p className="mt-1 text-sm font-semibold font-mono tabular text-ink-900">{formatINRCompact(v)}</p>
                      </div>
                    ))}
                  </div>
                </Card>
                <Card>
                  <SectionTitle title="Promises to pay" hint={`${ptp.recovery_rate_pct}% of resolved promises were kept`} right={<Handshake className="w-4 h-4 text-slate-400" />} />
                  <div className="flex h-2.5 rounded-full overflow-hidden bg-background">
                    {[
                      [ptp.fulfilled_count, "bg-emerald-500"],
                      [ptp.pending_count, "bg-accent-400"],
                      [ptp.broken_count, "bg-rose-500"],
                    ].map(([n, c], i) => {
                      const total = ptp.fulfilled_count + ptp.pending_count + ptp.broken_count || 1;
                      return <div key={i} className={c as string} style={{ width: `${((n as number) / total) * 100}%` }} />;
                    })}
                  </div>
                  <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    {[
                      ["Kept", ptp.fulfilled_count, ptp.fulfilled_amount, "text-emerald-700"],
                      ["Pending", ptp.pending_count, ptp.pending_amount, "text-accent-700"],
                      ["Broken", ptp.broken_count, ptp.broken_amount, "text-rose-600"],
                    ].map(([k, n, amt, c]) => (
                      <div key={k as string}>
                        <dt className="text-slate-500">{k}</dt>
                        <dd className={`font-semibold font-mono ${c}`}>{n as number}</dd>
                        <dd className="text-[11px] font-mono text-slate-500">{formatINRCompact(amt as any)}</dd>
                      </div>
                    ))}
                  </dl>
                </Card>
              </div>
            </motion.div>

            <motion.div variants={rise}>
              <Card>
                <SectionTitle title="Largest balances" hint="Where receivables are concentrated" />
                <ul className="space-y-3">
                  {kpis.top_debtors.slice(0, 8).map((d: any, i: number) => (
                    <li key={d.customer_id} className="grid grid-cols-[1fr_auto] md:grid-cols-[220px_1fr_auto_auto] items-center gap-3">
                      <Link href={`/customers/${d.customer_id}`} className="text-sm font-semibold text-ink-900 hover:text-brand-600 truncate">
                        {d.customer_name}
                      </Link>
                      <div className="hidden md:block h-2 rounded-full bg-background overflow-hidden">
                        <motion.div
                          className="h-full rounded-full bg-brand-500"
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.min(100, (d.percentage_of_total / (kpis.top_debtors[0]?.percentage_of_total || 1)) * 100)}%` }}
                          transition={{ duration: 0.6, delay: i * 0.05 }}
                        />
                      </div>
                      <span className="hidden md:block">
                        <RiskBadge tier={d.risk_tier} />
                      </span>
                      <span className="text-right">
                        <span className="block text-sm font-mono font-semibold tabular text-ink-900">{formatINR(d.outstanding)}</span>
                        <span className="block text-[11px] text-slate-500">{d.percentage_of_total}% of total</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            </motion.div>

            <motion.div variants={rise}>
              <ModelPanel />
            </motion.div>
          </motion.div>
        ) : null}
      </PageBody>
    </div>
  );
}

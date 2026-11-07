"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  IndianRupee,
  AlertTriangle,
  TrendingUp,
  Percent,
  ArrowRight,
  ArrowUpRight,
  Phone,
  ShieldAlert,
  Gavel,
  MessageSquare,
  CalendarClock,
  Hourglass,
  Flame,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import AgingChart from "@/components/AgingChart";
import TrendChart from "@/components/TrendChart";
import Badge from "@/components/Badge";
import { CardSkeleton } from "@/components/Skeleton";
import { PageBody, Card, SectionTitle, StatCard, AnimatedNumber, stagger, rise } from "@/components/ui";
import { formatINR, apiFetch } from "@/lib/api";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

const LANE_META = [
  { key: "call", label: "Call today", icon: Phone, dot: "bg-emerald-400" },
  { key: "escalate", label: "Escalate", icon: ShieldAlert, dot: "bg-rose-400" },
  { key: "resolve", label: "Resolve", icon: Gavel, dot: "bg-accent-400" },
  { key: "message", label: "Message", icon: MessageSquare, dot: "bg-brand-300" },
] as const;

export default function DashboardPage() {
  const [summary, setSummary] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [today, setToday] = useState<any>(null);
  const [me, setMe] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setIsRefreshing(true);
    try {
      const [s, t, td, m] = await Promise.all([
        apiFetch<any>("/dashboard/summary"),
        apiFetch<any[]>("/dashboard/trend?months=6"),
        apiFetch<any>("/collections/today"),
        apiFetch<any>("/auth/me").catch(() => null),
      ]);
      setSummary(s);
      setTrends(t);
      setToday(td);
      setMe(m);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard data");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const firstName = me?.full_name?.split(" ")[0];
  const money = (n: number) => formatINR(n);

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title="Overview"
        subtitle="Where your receivables stand and what to do about them"
        breadcrumbs={[{ label: "Udhaar Ledger" }, { label: "Overview" }]}
        onRefresh={load}
        isRefreshing={isRefreshing}
      />

      <PageBody>
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-ink-900">
            {greeting()}
            {firstName ? `, ${firstName}` : ""}
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">Here is how collections look right now.</p>
        </div>

        {error && (
          <div role="alert" className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center justify-between">
            <span className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600" />
              {error}
            </span>
            <button onClick={load} className="font-semibold underline hover:no-underline">
              Retry
            </button>
          </div>
        )}

        {isLoading && !summary ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              {[0, 1, 2, 3].map((i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
            <div className="h-56 surface animate-pulse" />
          </div>
        ) : summary ? (
          <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
            {/* KPIs */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <StatCard
                label="Total outstanding"
                value={Number(summary.total_outstanding)}
                format={money}
                icon={IndianRupee}
                tone="brand"
                foot="Open invoices, net of allocated payments"
              />
              <StatCard
                label="Overdue"
                value={Number(summary.total_overdue)}
                format={money}
                icon={AlertTriangle}
                tone="danger"
                foot={<span className="text-rose-600 font-medium">{summary.overdue_count} invoices past terms</span>}
              />
              <StatCard
                label="Collected this month"
                value={Number(summary.collected_this_month)}
                format={money}
                icon={TrendingUp}
                tone="success"
                foot="Payments received, by receipt date"
              />
              <StatCard
                label="Collected vs billed"
                value={Number(summary.collection_rate_pct)}
                format={(n) => `${n.toFixed(1)}%`}
                icon={Percent}
                tone="accent"
                foot="Cumulative, all invoices"
              />
            </div>

            {/* Today at a glance */}
            {today && (
              <motion.section
                variants={rise}
                className="relative overflow-hidden rounded-2xl bg-hero-ink text-white shadow-elevated"
              >
                <div className="absolute inset-0 bg-ledger-grid [background-size:32px_32px] opacity-50" aria-hidden />
                <div className="relative p-6 md:p-7 grid lg:grid-cols-[1fr_1.35fr] gap-8">
                  <div className="flex flex-col">
                    <div className="inline-flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.16em] text-accent-300">
                      <Flame className="w-3.5 h-3.5" /> Today at a glance
                    </div>
                    <h3 className="mt-3 text-2xl font-semibold tracking-tight leading-snug">
                      {today.call.length > 0
                        ? `${today.call.length} ${today.call.length === 1 ? "call" : "calls"} worth making today`
                        : "No calls needed today"}
                    </h3>
                    <p className="mt-1.5 text-sm text-brand-200/80">
                      Ranked by recoverable rupees, not by name or balance.
                    </p>
                    <div className="mt-6 grid grid-cols-2 gap-3">
                      {LANE_META.map((l) => (
                        <div key={l.key} className="rounded-xl bg-white/[0.06] ring-1 ring-white/10 px-3.5 py-3">
                          <div className="flex items-center gap-2 text-[11px] text-brand-200/80">
                            <span className={`w-1.5 h-1.5 rounded-full ${l.dot}`} />
                            {l.label}
                          </div>
                          <div className="mt-1 text-2xl font-semibold font-mono">
                            <AnimatedNumber value={today[l.key].length} />
                          </div>
                        </div>
                      ))}
                    </div>
                    {today.data_stale && (
                      <p className="mt-4 text-xs text-accent-200 flex items-start gap-2">
                        <Hourglass className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                        {today.days_since_last_receipt === null
                          ? "No receipts entered yet."
                          : `Last receipt entered ${today.days_since_last_receipt} days ago.`}{" "}
                        Update receipts so paid retailers don&apos;t show as overdue.
                      </p>
                    )}
                    <Link
                      href="/today"
                      className="mt-6 self-start inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-accent-400 hover:bg-accent-300 text-ink-900 text-sm font-semibold transition-colors"
                    >
                      Open today&apos;s list <ArrowRight className="w-4 h-4" />
                    </Link>
                  </div>

                  <ul className="space-y-2.5">
                    {today.call.slice(0, 3).map((a: any, i: number) => (
                      <motion.li
                        key={a.customer_id}
                        initial={{ opacity: 0, x: 16 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.25 + i * 0.1 }}
                        className="rounded-xl bg-white/[0.07] ring-1 ring-white/10 p-4 hover:bg-white/10 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <Link href={`/customers/${a.customer_id}`} className="font-semibold text-sm hover:underline">
                            {a.customer_name}
                          </Link>
                          <span className="font-mono font-semibold text-accent-300 text-sm whitespace-nowrap">
                            {formatINR(a.overdue_amount)}
                          </span>
                        </div>
                        <p className="mt-1.5 text-xs leading-relaxed text-brand-100/80">{a.reason}</p>
                      </motion.li>
                    ))}
                    {today.call.length === 0 && (
                      <li className="rounded-xl bg-white/[0.06] ring-1 ring-white/10 p-5 text-sm text-brand-100/80">
                        Nothing overdue is worth a call right now.
                      </li>
                    )}
                  </ul>
                </div>
              </motion.section>
            )}

            {/* Operational band */}
            <motion.div variants={rise} className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {[
                { icon: CalendarClock, tint: "bg-brand-50 text-brand-600", value: `${summary.invoices_due_this_week} due this week`, body: "A reminder before terms expire is the gentlest nudge." },
                { icon: Phone, tint: "bg-accent-50 text-accent-600", value: `${summary.pending_follow_ups} follow-ups pending`, body: "Open promises and calls not yet logged as done." },
                { icon: ShieldAlert, tint: "bg-rose-50 text-rose-600", value: formatINR(summary.high_risk_outstanding), body: "Outstanding with customers tagged high risk." },
              ].map((c) => (
                <Card key={c.value} className="flex items-center gap-3.5 !p-4">
                  <span className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${c.tint}`}>
                    <c.icon className="w-[18px] h-[18px]" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-ink-900 tabular">{c.value}</p>
                    <p className="text-xs text-slate-500 truncate">{c.body}</p>
                  </div>
                </Card>
              ))}
            </motion.div>

            {/* Charts */}
            <motion.div variants={rise} className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <Card className="flex flex-col">
                <SectionTitle
                  title="Receivables aging"
                  hint="Unpaid balance by days past due date"
                  right={<Badge variant="neutral" size="sm">Deterministic</Badge>}
                />
                <div className="flex-1">
                  <AgingChart data={summary.aging_buckets} />
                </div>
                <div className="mt-4 pt-4 border-t border-border-light grid grid-cols-5 gap-1.5 text-center">
                  {summary.aging_buckets?.map((b: any) => (
                    <div key={b.label} className="p-2 rounded-lg bg-background">
                      <p className="text-[10px] text-slate-500 truncate font-medium">{b.label}</p>
                      <p className="font-mono font-semibold text-ink-900 text-xs mt-0.5 tabular">{formatINR(b.amount)}</p>
                      <p className="text-[10px] text-slate-400 font-mono">{b.percentage}%</p>
                    </div>
                  ))}
                </div>
              </Card>

              <Card className="flex flex-col">
                <SectionTitle
                  title="Billed vs collected"
                  hint="Last six months"
                  right={
                    <Link href="/analytics" className="text-xs font-semibold text-brand-600 hover:text-brand-800 inline-flex items-center gap-1">
                      Analytics <ArrowUpRight className="w-3 h-3" />
                    </Link>
                  }
                />
                <div className="flex-1">
                  <TrendChart data={trends} />
                </div>
              </Card>
            </motion.div>
          </motion.div>
        ) : null}
      </PageBody>
    </div>
  );
}

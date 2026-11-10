"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Phone, Mail, ChevronRight, Users2 } from "lucide-react";
import Navbar from "@/components/Navbar";
import { RiskBadge } from "@/components/Badge";
import { PageBody, Toolbar, SearchInput, Segmented, Pagination, ErrorBanner, SkeletonRows, tbl } from "@/components/ui";
import { formatINR, apiFetch } from "@/lib/api";

type Tier = "" | "high" | "medium" | "low";

function Avatar({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <span className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-100 to-brand-50 text-brand-700 ring-1 ring-brand-200 flex items-center justify-center text-xs font-bold flex-shrink-0">
      {initials}
    </span>
  );
}

function Utilisation({ outstanding, limit }: { outstanding: number; limit: number }) {
  const pct = limit > 0 ? (outstanding / limit) * 100 : 0;
  const bar = pct > 100 ? "bg-rose-500" : pct > 75 ? "bg-accent-500" : "bg-emerald-500";
  return (
    <div className="min-w-[120px]">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-slate-500 font-mono tabular">{formatINR(limit)}</span>
        <span className={`font-semibold tabular ${pct > 100 ? "text-rose-600" : "text-slate-600"}`}>{pct.toFixed(0)}%</span>
      </div>
      <div className="mt-1.5 h-1.5 rounded-full bg-background overflow-hidden">
        <motion.div
          className={`h-full ${bar}`}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(100, pct)}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const perPage = 25;
  const [tier, setTier] = useState<Tier>("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      let url = `/customers?page=${page}&page_size=${perPage}`;
      if (tier) url += `&risk_tier=${tier}`;
      if (debounced.trim()) url += `&search=${encodeURIComponent(debounced.trim())}`;
      const data = await apiFetch<any>(url);
      setCustomers(data.items || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err.message || "Failed to load customers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, tier, debounced]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title="Customers"
        subtitle="Retailers, their terms, credit limits and live exposure"
        breadcrumbs={[{ label: "Udhaar Ledger" }, { label: "Books" }, { label: "Customers" }]}
        onRefresh={load}
        isRefreshing={loading}
      />

      <PageBody>
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink-900">
            <span className="tabular">{total.toLocaleString("en-IN")}</span> customers
          </h2>
          <p className="mt-1 text-sm text-slate-500">Credit use is outstanding balance against the agreed limit.</p>
        </div>

        <Toolbar>
          <SearchInput value={search} onChange={setSearch} placeholder="Search by customer name" />
          <Segmented<Tier>
            label="risk"
            value={tier}
            onChange={(v) => {
              setTier(v);
              setPage(1);
            }}
            options={[
              { value: "", label: "All" },
              { value: "high", label: "High risk" },
              { value: "medium", label: "Medium" },
              { value: "low", label: "Low" },
            ]}
          />
        </Toolbar>

        {error && <ErrorBanner message={error} onRetry={load} />}

        <div className="surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className={tbl.table}>
              <thead className={tbl.thead}>
                <tr>
                  <th scope="col" className={tbl.th}>Customer</th>
                  <th scope="col" className={tbl.th}>GSTIN</th>
                  <th scope="col" className={tbl.th}>Terms</th>
                  <th scope="col" className={tbl.th}>Credit used</th>
                  <th scope="col" className={`${tbl.th} text-right`}>Outstanding</th>
                  <th scope="col" className={`${tbl.th} text-right`}>Overdue</th>
                  <th scope="col" className={tbl.th}>Risk</th>
                  <th scope="col" className={tbl.th}></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <SkeletonRows cols={8} />
                ) : customers.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-16 text-center">
                      <Users2 className="w-8 h-8 text-slate-300 mx-auto" />
                      <p className="mt-2 text-sm font-semibold text-ink-900">No customers found</p>
                    </td>
                  </tr>
                ) : (
                  customers.map((c, i) => (
                    <motion.tr
                      key={c.id}
                      className={`${tbl.tr} group`}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: Math.min(i, 12) * 0.025 }}
                    >
                      <td className={tbl.td}>
                        <div className="flex items-center gap-3">
                          <Avatar name={c.name} />
                          <div className="min-w-0">
                            <Link href={`/customers/${c.id}`} className="font-semibold text-ink-900 hover:text-brand-600">
                              {c.name}
                            </Link>
                            <div className="flex flex-wrap gap-x-3 text-[11px] text-slate-500">
                              {c.phone && (
                                <span className="inline-flex items-center gap-1">
                                  <Phone className="w-3 h-3" /> {c.phone}
                                </span>
                              )}
                              {c.email && (
                                <span className="inline-flex items-center gap-1 truncate max-w-[180px]">
                                  <Mail className="w-3 h-3" /> {c.email}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className={`${tbl.td} font-mono text-[11px] text-slate-500`}>{c.gst_number || "—"}</td>
                      <td className={`${tbl.td} text-xs text-slate-600 whitespace-nowrap`}>{c.payment_terms_days || 30} days</td>
                      <td className={tbl.td}>
                        <Utilisation outstanding={Number(c.total_outstanding || 0)} limit={Number(c.credit_limit || 0)} />
                      </td>
                      <td className={`${tbl.td} text-right font-mono font-semibold tabular text-ink-900`}>
                        {formatINR(c.total_outstanding)}
                      </td>
                      <td
                        className={`${tbl.td} text-right font-mono tabular ${
                          Number(c.total_overdue) > 0 ? "text-rose-600 font-semibold" : "text-slate-400"
                        }`}
                      >
                        {formatINR(c.total_overdue)}
                      </td>
                      <td className={tbl.td}>
                        <RiskBadge tier={c.risk_tier} />
                      </td>
                      <td className={`${tbl.td} text-right`}>
                        <Link
                          href={`/customers/${c.id}`}
                          aria-label={`Open ${c.name}`}
                          className="h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate-400 group-hover:text-brand-600 hover:bg-brand-50"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </Link>
                      </td>
                    </motion.tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={totalPages} total={total} noun="customers" onPage={setPage} disabled={loading} />
        </div>
      </PageBody>
    </div>
  );
}

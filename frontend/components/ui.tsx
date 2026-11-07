"use client";

import { useEffect } from "react";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";

/** Standard page body: consistent gutters and max width. */
export function PageBody({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`p-5 md:p-8 space-y-6 max-w-[1400px] mx-auto w-full ${className}`}>{children}</div>;
}

export const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
};
export const rise = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" as const } },
};

export function Card({
  children,
  className = "",
  padded = true,
}: {
  children: React.ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return <div className={`surface ${padded ? "p-5" : ""} ${className}`}>{children}</div>;
}

export function SectionTitle({
  title,
  hint,
  right,
}: {
  title: string;
  hint?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 mb-4">
      <div>
        <h3 className="text-sm font-semibold text-ink-900 tracking-tight">{title}</h3>
        {hint && <p className="text-xs text-slate-500 mt-0.5">{hint}</p>}
      </div>
      {right}
    </div>
  );
}

/** Counts up to `value` when it first appears or changes. */
export function AnimatedNumber({
  value,
  format = (n: number) => Math.round(n).toLocaleString("en-IN"),
  className = "",
}: {
  value: number;
  format?: (n: number) => string;
  className?: string;
}) {
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => format(v));
  useEffect(() => {
    const controls = animate(mv, value, { duration: 0.9, ease: "easeOut" });
    return () => controls.stop();
  }, [value, mv]);
  return <motion.span className={`tabular ${className}`}>{text}</motion.span>;
}

const TONES = {
  brand: { bar: "bg-brand-500", icon: "bg-brand-50 text-brand-600", value: "text-ink-900" },
  danger: { bar: "bg-rose-500", icon: "bg-rose-50 text-rose-600", value: "text-rose-600" },
  success: { bar: "bg-emerald-500", icon: "bg-emerald-50 text-emerald-600", value: "text-emerald-700" },
  accent: { bar: "bg-accent-500", icon: "bg-accent-50 text-accent-600", value: "text-ink-900" },
} as const;

export function StatCard({
  label,
  value,
  format,
  foot,
  icon: Icon,
  tone = "brand",
}: {
  label: string;
  value: number;
  format?: (n: number) => string;
  foot?: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  tone?: keyof typeof TONES;
}) {
  const t = TONES[tone];
  return (
    <motion.div
      variants={rise}
      whileHover={{ y: -2 }}
      className="surface relative overflow-hidden p-5 transition-shadow hover:shadow-elevated"
    >
      <span className={`absolute left-0 top-0 h-full w-1 ${t.bar}`} aria-hidden />
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-500">{label}</span>
        <span className={`w-8 h-8 rounded-lg flex items-center justify-center ${t.icon}`}>
          <Icon className="w-4 h-4" />
        </span>
      </div>
      <div className={`mt-3 text-[26px] leading-none font-semibold font-mono tracking-tight ${t.value}`}>
        <AnimatedNumber value={value} format={format} />
      </div>
      {foot && <div className="mt-3 pt-3 border-t border-border-light text-xs text-slate-500">{foot}</div>}
    </motion.div>
  );
}

export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div className="py-10 text-center">
      <p className="text-sm font-medium text-slate-600">{title}</p>
      {body && <p className="text-xs text-slate-400 mt-1">{body}</p>}
    </div>
  );
}

/* ---------- List-page building blocks ---------- */

export function Toolbar({ children }: { children: React.ReactNode }) {
  return (
    <div className="surface p-3 flex flex-col xl:flex-row xl:items-center justify-between gap-3">{children}</div>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  label = "Search",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  label?: string;
}) {
  return (
    <label className="relative flex-1 w-full xl:max-w-md">
      <span className="sr-only">{label}</span>
      <svg aria-hidden className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full h-10 pl-10 pr-3 bg-background border border-border rounded-xl text-sm text-ink-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 focus:bg-white transition"
      />
    </label>
  );
}

export function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string | number;
  onChange: (v: string) => void;
  options: { value: string | number; label: string }[];
}) {
  return (
    <label className="flex items-center gap-2 text-xs">
      <span className="text-slate-500 font-medium whitespace-nowrap">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 pl-3 pr-8 bg-white border border-border rounded-xl text-xs font-medium text-ink-900 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex p-1 rounded-xl bg-background border border-border">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`relative h-8 px-3 rounded-lg text-xs font-semibold transition-colors ${
              active ? "text-ink-900" : "text-slate-500 hover:text-ink-900"
            }`}
          >
            {active && (
              <motion.span
                layoutId={`seg-${label}`}
                className="absolute inset-0 rounded-lg bg-white shadow-card ring-1 ring-border"
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export function Pagination({
  page,
  totalPages,
  total,
  noun,
  onPage,
  disabled,
}: {
  page: number;
  totalPages: number;
  total: number;
  noun: string;
  onPage: (p: number) => void;
  disabled?: boolean;
}) {
  const btn =
    "h-9 px-3 rounded-xl border border-border bg-white hover:bg-background text-xs font-medium disabled:opacity-40 disabled:cursor-not-allowed";
  return (
    <div className="px-5 py-3 border-t border-border-light flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
      <span>
        <span className="font-semibold text-ink-900 tabular">{total.toLocaleString("en-IN")}</span> {noun} · page{" "}
        <span className="tabular">{page}</span> of <span className="tabular">{totalPages}</span>
      </span>
      <div className="flex items-center gap-2">
        <button className={btn} onClick={() => onPage(page - 1)} disabled={disabled || page <= 1}>
          Previous
        </button>
        <button className={btn} onClick={() => onPage(page + 1)} disabled={disabled || page >= totalPages}>
          Next
        </button>
      </div>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center justify-between gap-3">
      <span>{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="font-semibold underline hover:no-underline">
          Retry
        </button>
      )}
    </div>
  );
}

/** Shared table classes so every list looks the same. */
export const tbl = {
  table: "w-full text-left text-[13px]",
  thead: "bg-background/70 text-[11px] uppercase tracking-[0.08em] text-slate-500 border-b border-border",
  th: "py-3 px-4 font-semibold whitespace-nowrap",
  tr: "border-b border-border-light last:border-0 hover:bg-brand-50/40 transition-colors",
  td: "py-3.5 px-4 align-middle",
  nowrap: "whitespace-nowrap",
};

export function SkeletonRows({ rows = 8, cols }: { rows?: number; cols: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="border-b border-border-light">
          {Array.from({ length: cols }).map((__, j) => (
            <td key={j} className="py-4 px-4">
              <div className={`h-3.5 rounded bg-background animate-pulse ${j === 1 ? "w-40" : "w-20"}`} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

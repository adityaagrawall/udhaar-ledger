import React from "react";

export type BadgeVariant =
  | "default"
  | "brand"
  | "success"
  | "warning"
  | "danger"
  | "neutral";

export type BadgeSize = "sm" | "md";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  className?: string;
}

const variantStyles: Record<BadgeVariant, { bg: string; text: string; border: string; dot: string }> = {
  default: {
    bg: "bg-slate-100",
    text: "text-slate-700",
    border: "border-slate-200/80",
    dot: "bg-slate-400",
  },
  neutral: {
    bg: "bg-slate-50",
    text: "text-slate-600",
    border: "border-slate-200",
    dot: "bg-slate-400",
  },
  brand: {
    bg: "bg-brand-50",
    text: "text-brand-700",
    border: "border-brand-200/80",
    dot: "bg-brand-500",
  },
  success: {
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    border: "border-emerald-200/80",
    dot: "bg-emerald-500",
  },
  warning: {
    bg: "bg-amber-50",
    text: "text-amber-700",
    border: "border-amber-200/80",
    dot: "bg-amber-500",
  },
  danger: {
    bg: "bg-rose-50",
    text: "text-rose-700",
    border: "border-rose-200/80",
    dot: "bg-rose-500",
  },
};

export default function Badge({
  children,
  variant = "default",
  size = "md",
  dot = false,
  className = "",
}: BadgeProps) {
  const styles = variantStyles[variant] || variantStyles.default;
  const sizeClasses =
    size === "sm"
      ? "text-[10px] px-1.5 py-0.5 tracking-tight font-medium"
      : "text-xs px-2 py-0.5 font-medium";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${styles.bg} ${styles.text} ${styles.border} ${sizeClasses} ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${styles.dot}`} />}
      {children}
    </span>
  );
}

export function RiskBadge({ tier }: { tier?: string | null }) {
  const t = (tier || "medium").toLowerCase();
  if (t === "high") {
    return <Badge variant="danger" size="sm" dot>High Risk</Badge>;
  }
  if (t === "low") {
    return <Badge variant="success" size="sm" dot>Low Risk</Badge>;
  }
  return <Badge variant="warning" size="sm" dot>Medium Risk</Badge>;
}

export function StatusBadge({ status }: { status?: string | null }) {
  const s = (status || "draft").toLowerCase();
  switch (s) {
    case "paid":
      return <Badge variant="success" size="sm" dot>Paid</Badge>;
    case "overdue":
      return <Badge variant="danger" size="sm" dot>Overdue</Badge>;
    case "partial":
      return <Badge variant="warning" size="sm" dot>Partial</Badge>;
    case "sent":
      return <Badge variant="brand" size="sm" dot>Sent</Badge>;
    case "cancelled":
      return <Badge variant="neutral" size="sm">Cancelled</Badge>;
    default:
      return <Badge variant="default" size="sm">{status}</Badge>;
  }
}

import React from "react";

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse bg-slate-200/80 rounded-md ${className}`}
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="bg-white p-5 rounded-2xl border border-border shadow-card space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-7 w-7 rounded-lg" />
      </div>
      <Skeleton className="h-8 w-36" />
      <Skeleton className="h-3.5 w-44" />
    </div>
  );
}

export function TableRowSkeleton({ columns = 6 }: { columns?: number }) {
  return (
    <tr className="border-b border-slate-100">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="py-3.5 px-4">
          <Skeleton className={`h-4 ${i === 0 ? "w-28" : i === 1 ? "w-40" : "w-20"}`} />
        </td>
      ))}
    </tr>
  );
}

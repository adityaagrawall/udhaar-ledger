import React from "react";

/** Udhaar Ledger mark: a "U" that doubles as an open ledger page, with a saffron tick for a cleared account. */
export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  const id = React.useId().replace(/:/g, "");
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      role="img"
      aria-label="Udhaar Ledger"
      className={className}
    >
      <defs>
        <linearGradient id={`${id}-bg`} x1="6" y1="4" x2="58" y2="60" gradientUnits="userSpaceOnUse">
          <stop stopColor="#2B4BC7" />
          <stop offset="1" stopColor="#0B1330" />
        </linearGradient>
        <linearGradient id={`${id}-gold`} x1="24" y1="22" x2="46" y2="42" gradientUnits="userSpaceOnUse">
          <stop stopColor="#FCD34D" />
          <stop offset="1" stopColor="#F59E0B" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill={`url(#${id}-bg)`} />
      <rect x="1" y="1" width="62" height="62" rx="15" stroke="#fff" strokeOpacity=".14" strokeWidth="2" />
      <path d="M18 13v21a14 14 0 0 0 28 0V13" stroke="#fff" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M25.5 31.5 31 37l10-13" stroke={`url(#${id}-gold)`} strokeWidth="5.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 52h36" stroke="#fff" strokeOpacity=".28" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export default function Logo({
  size = 32,
  tone = "light",
  tagline = false,
}: {
  size?: number;
  tone?: "light" | "dark";
  tagline?: boolean;
}) {
  const text = tone === "light" ? "text-white" : "text-ink-900";
  const sub = tone === "light" ? "text-brand-200/80" : "text-slate-500";
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark size={size} />
      <span className="leading-none">
        <span className={`block font-semibold tracking-tight ${text}`} style={{ fontSize: size * 0.5 }}>
          Udhaar <span className="text-accent-400">Ledger</span>
        </span>
        {tagline && (
          <span className={`block mt-1 text-[10px] uppercase tracking-[0.14em] ${sub}`}>Decision layer for credit</span>
        )}
      </span>
    </span>
  );
}

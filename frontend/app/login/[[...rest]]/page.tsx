"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { SignIn, useSignIn } from "@clerk/nextjs";
import { motion } from "framer-motion";
import { Eye, ArrowRight, AlertCircle } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import { API_BASE } from "@/lib/api";

function DemoButton() {
  const { isLoaded, signIn, setActive } = useSignIn();
  const router = useRouter();
  const params = useSearchParams();
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/auth/config`)
      .then((r) => r.json())
      .then((c) => setEnabled(Boolean(c.demo_enabled)))
      .catch(() => setEnabled(false));
  }, []);

  if (!enabled) return null;

  const start = async () => {
    if (!isLoaded) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/demo`, { method: "POST" });
      if (!res.ok) throw new Error((await res.json()).detail || "Demo is unavailable right now.");
      const { ticket } = await res.json();
      const attempt = await signIn.create({ strategy: "ticket", ticket });
      if (attempt.status !== "complete") throw new Error("Demo sign-in did not complete.");
      await setActive({ session: attempt.createdSessionId });
      router.push(params.get("redirect_url") || "/today");
    } catch (e: any) {
      setError(e?.errors?.[0]?.longMessage || e.message || "Demo is unavailable right now.");
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <motion.button
        onClick={start}
        disabled={busy || !isLoaded}
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.98 }}
        className="group w-full flex items-center justify-between gap-3 p-4 rounded-2xl bg-hero-ink text-left text-white shadow-elevated ring-1 ring-brand-700 disabled:opacity-70"
      >
        <span className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-xl bg-accent-400 text-ink-900 flex items-center justify-center flex-shrink-0">
            {busy ? (
              <span className="w-4 h-4 border-2 border-ink-900/30 border-t-ink-900 rounded-full animate-spin" />
            ) : (
              <Eye className="w-5 h-5" />
            )}
          </span>
          <span>
            <span className="block text-sm font-semibold">{busy ? "Opening the demo…" : "Explore the live demo"}</span>
            <span className="block text-xs text-brand-200/80">No sign-up. Read-only, with synthetic data.</span>
          </span>
        </span>
        <ArrowRight className="w-4 h-4 text-accent-300 transition-transform group-hover:translate-x-0.5" />
      </motion.button>
      {error && (
        <p role="alert" className="flex items-start gap-2 text-xs text-rose-700">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5" /> {error}
        </p>
      )}
      <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.14em] text-slate-400">
        <span className="h-px flex-1 bg-border" /> or sign in <span className="h-px flex-1 bg-border" />
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <AuthShell>
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Welcome to Udhaar Ledger</h1>
      <p className="mt-1 mb-6 text-sm text-slate-500">See today&apos;s collection list in seconds.</p>
      <DemoButton />
      <div className="mt-4">
        <SignIn routing="path" path="/login" signUpUrl="/sign-up" fallbackRedirectUrl="/" />
      </div>
    </AuthShell>
  );
}

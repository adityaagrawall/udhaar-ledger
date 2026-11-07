"use client";

import { motion } from "framer-motion";
import { ListChecks, MessageSquareText, HandHelping } from "lucide-react";
import Logo from "@/components/Logo";

const POINTS = [
  { icon: ListChecks, title: "A short list, ranked by recoverable rupees", body: "Not by name or balance. Lanes separate calls from decisions and disputes." },
  { icon: MessageSquareText, title: "Every row explains itself", body: "Plain-language reasons you can overrule, generated from the same factors as the score." },
  { icon: HandHelping, title: "You stay in control", body: "Nothing is sent automatically. Every reminder is reviewed and approved by a person." },
];

export default function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen w-full grid lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden lg:flex flex-col justify-between p-12 bg-hero-ink text-white overflow-hidden">
        <div className="absolute inset-0 bg-ledger-grid [background-size:36px_36px] opacity-60" aria-hidden />
        <div className="absolute -bottom-40 -left-24 w-[520px] h-[520px] rounded-full bg-accent-400/10 blur-3xl" aria-hidden />
        <div className="relative">
          <Logo size={40} tagline />
        </div>
        <div className="relative max-w-lg">
          <motion.h2
            className="text-4xl font-semibold tracking-tight leading-[1.15]"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            Chase the right retailer,
            <br />
            <span className="text-accent-400">not the biggest balance.</span>
          </motion.h2>
          <ul className="mt-10 space-y-6">
            {POINTS.map((p, i) => (
              <motion.li
                key={p.title}
                className="flex gap-4"
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.25 + i * 0.12, duration: 0.4 }}
              >
                <span className="mt-0.5 w-9 h-9 flex-shrink-0 rounded-xl bg-white/10 ring-1 ring-white/15 flex items-center justify-center">
                  <p.icon className="w-[18px] h-[18px] text-accent-300" />
                </span>
                <span>
                  <span className="block text-sm font-semibold">{p.title}</span>
                  <span className="block text-sm text-brand-200/80 leading-relaxed">{p.body}</span>
                </span>
              </motion.li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-brand-200/60">Built for Indian distributors and wholesalers.</p>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-10 bg-background">
        <motion.div
          className="w-full max-w-[400px]"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          <div className="lg:hidden mb-8">
            <Logo size={38} tone="dark" />
          </div>
          {children}
        </motion.div>
      </div>
    </div>
  );
}

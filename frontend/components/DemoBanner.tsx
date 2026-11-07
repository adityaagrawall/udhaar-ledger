"use client";

import Link from "next/link";
import { Eye } from "lucide-react";
import { useMe } from "@/components/Providers";

/** Shown to read-only viewers so they know why edit actions are unavailable. */
export default function DemoBanner() {
  const { me } = useMe();
  if (!me || me.role !== "viewer") return null;
  return (
    <div className="bg-ink-900 text-white text-xs">
      <div className="max-w-[1400px] mx-auto px-5 md:px-8 py-2 flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-start gap-2">
          <Eye className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-accent-300" />
          <span>
          {me.is_demo ? (
            <>
              You&apos;re exploring a <strong className="font-semibold text-accent-300">read-only demo</strong> with
              synthetic data for a fictional distributor. Look around freely; nothing can be changed.
            </>
          ) : (
            <>You have read-only access. Ask an admin for edit rights.</>
          )}
          </span>
        </span>
        {me.is_demo && (
          <Link href="/today" className="font-semibold text-accent-300 hover:text-accent-200 whitespace-nowrap">
            Start with Today&apos;s list →
          </Link>
        )}
      </div>
    </div>
  );
}

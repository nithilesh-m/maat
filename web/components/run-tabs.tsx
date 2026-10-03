"use client";
import { motion } from "framer-motion";
import Link from "next/link";

const TABS = [
  ["", "Overview"],
  ["/clauses", "Clauses"],
  ["/findings", "Findings"],
  ["/remediation", "Remediation"],
  ["/bundle", "Bundle"],
];

export function RunTabs({ runId, active }: { runId: string; active: string }) {
  return (
    <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-border" aria-label="Run sections">
      {TABS.map(([suffix, label]) => (
        <Link
          key={label}
          href={`/runs/${runId}${suffix}`}
          aria-current={active === label ? "page" : undefined}
          className={`relative px-4 py-3 text-sm outline-none transition focus-visible:ring-3 focus-visible:ring-ring/50 ${
            active === label ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {label}
          {active === label && (
            <motion.span layoutId="run-tab" className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-primary" transition={{ type: "spring", stiffness: 500, damping: 40 }} />
          )}
        </Link>
      ))}
    </nav>
  );
}

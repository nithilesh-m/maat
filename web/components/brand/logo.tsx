"use client";
import { motion } from "framer-motion";

/** MAAT mark: the scales of Ma'at (truth) as a chain of linked, hashed blocks. */
export function Logo({ size = 28, animated = false }: { size?: number; animated?: boolean }) {
  const draw = animated
    ? { initial: { pathLength: 0 }, animate: { pathLength: 1 }, transition: { duration: 1.4, ease: "easeOut" as const } }
    : {};
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <defs>
        <linearGradient id="logo-g" x1="2" y1="2" x2="30" y2="30">
          <stop offset="0" stopColor="var(--brand)" />
          <stop offset="1" stopColor="var(--brand-2)" />
        </linearGradient>
      </defs>
      <rect x="1.5" y="1.5" width="29" height="29" rx="9" stroke="url(#logo-g)" strokeWidth="1.6" opacity="0.5" />
      <motion.path d="M16 6v19" stroke="url(#logo-g)" strokeWidth="2.2" strokeLinecap="round" {...draw} />
      <motion.path d="M7 11l9-3 9 3" stroke="url(#logo-g)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" {...draw} />
      <motion.path d="M7 11l-3.2 7.5a3.6 3.6 0 0 0 6.4 0L7 11zM25 11l-3.2 7.5a3.6 3.6 0 0 0 6.4 0L25 11z" stroke="url(#logo-g)" strokeWidth="1.8" strokeLinejoin="round" {...draw} />
      <motion.path d="M11.5 26h9" stroke="url(#logo-g)" strokeWidth="2.2" strokeLinecap="round" {...draw} />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <Logo />
      <span className="text-[15px] font-semibold tracking-[0.18em]">MAAT</span>
    </span>
  );
}

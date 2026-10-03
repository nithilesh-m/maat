"use client";
import {
  animate,
  motion,
  useInView,
  useMotionValue,
  useReducedMotion,
  type HTMLMotionProps,
} from "framer-motion";
import { useEffect, useRef, useState } from "react";

const EASE = [0.2, 0.8, 0.2, 1] as const;

/** Fade and rise on mount. */
export function FadeIn({
  delay = 0,
  y = 14,
  className,
  children,
  ...rest
}: { delay?: number; y?: number } & HTMLMotionProps<"div">) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay, ease: EASE }}
      className={className}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/** Fade and rise when scrolled into view (once). */
export function Reveal({
  delay = 0,
  y = 24,
  className,
  children,
  ...rest
}: { delay?: number; y?: number } & HTMLMotionProps<"div">) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay, ease: EASE }}
      className={className}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.06, delayChildren: 0.04 } } };
const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE } },
};

export function Stagger({
  className,
  children,
  inView = false,
  ...rest
}: { inView?: boolean } & HTMLMotionProps<"div">) {
  const trigger = inView
    ? { whileInView: "show", viewport: { once: true, margin: "-60px" } }
    : { animate: "show" };
  return (
    <motion.div variants={stagger} initial="hidden" {...trigger} className={className} {...rest}>
      {children}
    </motion.div>
  );
}

export function StaggerItem({ className, children, ...rest }: HTMLMotionProps<"div">) {
  return (
    <motion.div variants={item} className={className} {...rest}>
      {children}
    </motion.div>
  );
}

/** Counts up to `value`. The final text is always the formatted API value. */
export function AnimatedNumber({
  value,
  format = (n: number) => n.toFixed(3),
  className,
  duration = 1.1,
}: {
  value: number | null | undefined;
  format?: (n: number) => string;
  className?: string;
  duration?: number;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const mv = useMotionValue(0);
  const [text, setText] = useState(value == null ? "–" : format(reduce ? value : 0));

  useEffect(() => {
    if (value == null) {
      setText("–");
      return;
    }
    if (reduce || !inView) {
      if (reduce) setText(format(value));
      return;
    }
    const controls = animate(mv, value, { duration, ease: EASE, onUpdate: (v) => setText(format(v)) });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, inView, reduce]);

  return (
    <span ref={ref} className={className} aria-label={value == null ? "no value" : format(value)}>
      {text}
    </span>
  );
}

/** Circular gauge for a 0..1 score. */
export function ScoreRing({
  value,
  label,
  size = 84,
  stroke = 8,
}: {
  value: number | null | undefined;
  label: string;
  size?: number;
  stroke?: number;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value ?? 0));
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-muted" />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            stroke="url(#ring-grad)"
            strokeDasharray={c}
            initial={{ strokeDashoffset: c }}
            animate={{ strokeDashoffset: c * (1 - v) }}
            transition={{ duration: 1.2, ease: EASE }}
          />
          <defs>
            <linearGradient id="ring-grad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="var(--brand)" />
              <stop offset="100%" stopColor="var(--brand-2)" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <AnimatedNumber value={value} className="text-sm font-semibold tabular-nums" />
        </div>
      </div>
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</span>
    </div>
  );
}

export { motion };

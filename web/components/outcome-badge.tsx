import { CheckCircle2, CircleDashed, CircleSlash, HelpCircle, ShieldAlert, XCircle } from "lucide-react";
import { outcomeTone } from "@/lib/format";
import type { GateOutcome } from "@/lib/types";

const TONE = {
  success: "bg-success/12 text-success ring-success/30",
  danger: "bg-destructive/12 text-destructive ring-destructive/30",
  warning: "bg-warning/15 text-[color-mix(in_oklch,var(--warning),var(--foreground)_35%)] ring-warning/35",
  muted: "bg-muted text-muted-foreground ring-border",
} as const;
const LABEL: Record<GateOutcome, string> = {
  pass: "pass",
  block: "block",
  fail: "fail",
  waive: "waive",
  abstain: "abstain",
  not_applicable: "n/a",
};
const ICON: Record<GateOutcome, typeof CheckCircle2> = {
  pass: CheckCircle2,
  block: ShieldAlert,
  fail: XCircle,
  waive: CircleDashed,
  abstain: HelpCircle,
  not_applicable: CircleSlash,
};

/** Colour plus text plus icon: outcome is never conveyed by colour alone. */
export function OutcomeBadge({ outcome }: { outcome: GateOutcome }) {
  const Icon = ICON[outcome];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE[outcomeTone(outcome)]}`}
    >
      <Icon className="size-3" aria-hidden />
      {LABEL[outcome]}
    </span>
  );
}

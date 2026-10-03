import type { RunStatus } from "@/lib/types";

const MAP: Record<RunStatus, { cls: string; live?: boolean }> = {
  queued: { cls: "bg-muted text-muted-foreground ring-border", live: true },
  running: { cls: "bg-info/12 text-info ring-info/30", live: true },
  paused: { cls: "bg-warning/15 text-[color-mix(in_oklch,var(--warning),var(--foreground)_35%)] ring-warning/35" },
  complete: { cls: "bg-success/12 text-success ring-success/30" },
  failed: { cls: "bg-destructive/12 text-destructive ring-destructive/30" },
};

export function StatusPill({ status }: { status: RunStatus }) {
  const m = MAP[status] ?? MAP.queued;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${m.cls}`}>
      <span className="relative flex size-1.5">
        {m.live && <span className="absolute inline-flex size-full animate-pulse-ring rounded-full bg-current opacity-60" />}
        <span className="relative inline-flex size-1.5 rounded-full bg-current" />
      </span>
      {status}
    </span>
  );
}

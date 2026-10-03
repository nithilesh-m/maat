import { AnimatePresence, motion } from "framer-motion";
import { Bot, CheckCircle2, CircleAlert, Gavel, ListTree, PlayCircle, ShieldCheck, Sparkles, Wrench, XCircle } from "lucide-react";
import type { MaatEvent } from "@/lib/types";

type P = Record<string, unknown>;
const META: Record<string, { text: (p: P) => string; icon: typeof Bot; tone: string }> = {
  classified: { text: (p) => `Classified: suggested tier ${p.suggested_tier}`, icon: Sparkles, tone: "text-brand" },
  approval_needed: { text: () => "Waiting for human approval", icon: CircleAlert, tone: "text-warning" },
  plan_created: { text: (p) => `Plan created (${p.planner})`, icon: ListTree, tone: "text-brand" },
  agent_started: { text: (p) => `${p.agent} agent started`, icon: Bot, tone: "text-info" },
  agent_finished: { text: (p) => `${p.agent} agent finished: ${p.findings} findings`, icon: Bot, tone: "text-success" },
  tool_started: { text: (p) => `Running ${p.tool}`, icon: PlayCircle, tone: "text-muted-foreground" },
  tool_finished: { text: (p) => `${p.tool} (${p.evidence_type})`, icon: Wrench, tone: "text-success" },
  gap: { text: (p) => `Gap on ${p.control_id}: ${p.reason}`, icon: CircleAlert, tone: "text-warning" },
  gate_decision: { text: (p) => `${p.control_id}: ${p.outcome}`, icon: Gavel, tone: "text-foreground" },
  run_sealed: { text: (p) => `Sealed ${String(p.bundle_id ?? "").slice(0, 22)}…`, icon: ShieldCheck, tone: "text-success" },
  run_failed: { text: (p) => `Failed: ${p.error}`, icon: XCircle, tone: "text-destructive" },
};

export function EventFeed({ events }: { events: MaatEvent[] }) {
  if (events.length === 0)
    return <p className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">Waiting for the first event…</p>;
  return (
    <ol className="relative space-y-1.5 border-l border-border pl-6" aria-live="polite">
      <AnimatePresence initial={false}>
        {events.map((e) => {
          const m = META[e.kind] ?? { text: () => `${e.kind} ${JSON.stringify(e.payload)}`, icon: CheckCircle2, tone: "text-muted-foreground" };
          return (
            <motion.li
              key={e.seq}
              layout
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25 }}
              className="relative flex items-start gap-3 rounded-xl px-3 py-1.5 font-mono text-[13px] hover:bg-muted/50"
            >
              <span className={`absolute -left-[2.2rem] top-1.5 grid size-5 place-items-center rounded-full bg-background ring-1 ring-border ${m.tone}`}>
                <m.icon className="size-3" aria-hidden />
              </span>
              <span className="w-8 shrink-0 text-xs text-muted-foreground tabular-nums">{e.seq}</span>
              <span>{m.text(e.payload)}</span>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ol>
  );
}

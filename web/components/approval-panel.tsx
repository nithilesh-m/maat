"use client";
import { load as loadYaml } from "js-yaml";
import { ArrowRight, Hand } from "lucide-react";
import { useState } from "react";
import { ErrorNote } from "@/components/page-header";
import { useApprove } from "@/lib/hooks";

export function ApprovalPanel({ runId, question }: { runId: string; question: Record<string, unknown> }) {
  const approve = useApprove(runId);
  const [ers, setErs] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const send = async (approve_tier: boolean) => {
    setErr(null);
    let parsed: unknown = null;
    if (ers.trim()) {
      try {
        parsed = loadYaml(ers);
      } catch (e) {
        setErr(`ERS YAML error: ${(e as Error).message}`);
        return;
      }
    }
    await approve.mutateAsync({ approve_tier, ers: parsed as Record<string, unknown> | null });
  };
  return (
    <section className="glow rounded-3xl border border-warning/40 bg-card p-6" aria-labelledby="approval-title">
      <div className="flex items-start gap-4">
        <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-warning/15 text-warning"><Hand className="size-5" /></span>
        <div className="min-w-0 flex-1 space-y-4">
          <div>
            <h2 id="approval-title" className="text-lg font-semibold">Approval needed</h2>
            <p className="mt-1 text-sm text-muted-foreground">The orchestrator classified the system and wants a human to confirm the risk tier before it plans the audit.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="rounded-lg bg-muted px-3 py-1.5">Declared tier <b>{String(question.declared_tier)}</b></span>
            <ArrowRight className="size-4 text-muted-foreground" aria-hidden />
            <span className="rounded-lg bg-primary/12 px-3 py-1.5 text-primary">Suggested <b>{String(question.suggested_tier)}</b></span>
          </div>
          <p className="text-sm text-muted-foreground">{String(question.rationale ?? "")}</p>
          {question.ers_missing ? (
            <div>
              <label htmlFor="ers" className="text-sm font-medium">Optional ERS (YAML)</label>
              <textarea id="ers" rows={5} value={ers} onChange={(e) => setErs(e.target.value)} className="mt-1.5 w-full rounded-xl border border-input bg-background p-3 font-mono text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/40" />
            </div>
          ) : null}
          {err && <p role="alert" className="text-sm text-destructive">{err}</p>}
          <ErrorNote error={approve.error} />
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => send(true)} disabled={approve.isPending} className="h-10 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50">Accept suggested tier</button>
            <button type="button" onClick={() => send(false)} disabled={approve.isPending} className="h-10 rounded-xl border border-border bg-background px-4 text-sm font-medium transition hover:bg-muted disabled:opacity-50">Keep declared tier</button>
          </div>
        </div>
      </div>
    </section>
  );
}

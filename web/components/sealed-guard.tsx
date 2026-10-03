"use client";
import { Loader2, OctagonAlert } from "lucide-react";
import Link from "next/link";
import { ApprovalPanel } from "@/components/approval-panel";
import { SkeletonRows } from "@/components/page-header";
import { useRun } from "@/lib/hooks";

/** Review Focus #3: unsealed and paused runs get a clear state, never an error page. */
export function SealedGuard({ runId, children }: { runId: string; children: React.ReactNode }) {
  const run = useRun(runId);
  if (run.isLoading || !run.data) return <SkeletonRows />;
  const s = run.data.status;
  if (s === "queued" || s === "running")
    return (
      <div className="flex items-center gap-4 rounded-2xl border border-border bg-card p-6">
        <Loader2 className="size-5 animate-spin text-brand" aria-hidden />
        <p>
          Audit in progress.{" "}
          <Link className="font-medium text-primary underline-offset-4 hover:underline" href={`/runs/${runId}/live`}>
            Watch live →
          </Link>
        </p>
      </div>
    );
  if (s === "paused")
    return run.data.pending_approval ? (
      <ApprovalPanel runId={runId} question={run.data.pending_approval} />
    ) : (
      <p className="rounded-2xl border border-border bg-card p-6">Awaiting approval.</p>
    );
  if (s === "failed")
    return (
      <p role="alert" className="flex items-start gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 p-5 text-destructive">
        <OctagonAlert className="mt-0.5 size-5 shrink-0" aria-hidden />
        <span>Run failed: {run.data.error}</span>
      </p>
    );
  return <>{children}</>;
}

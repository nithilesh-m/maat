"use client";
import { PageHeader } from "@/components/page-header";
import { RunTabs } from "@/components/run-tabs";
import { SealedGuard } from "@/components/sealed-guard";
import { StatusPill } from "@/components/status-pill";
import { useRun } from "@/lib/hooks";

/** Common header, tabs and sealed-state guard for every bundle-derived page. */
export function RunFrame({ id, active, children }: { id: string; active: string; children: React.ReactNode }) {
  const run = useRun(id);
  return (
    <>
      <PageHeader
        eyebrow="Run"
        title={<span className="font-mono text-2xl sm:text-3xl">{id}</span>}
        actions={run.data && <StatusPill status={run.data.status} />}
      />
      <RunTabs runId={id} active={active} />
      <SealedGuard runId={id}>{children}</SealedGuard>
    </>
  );
}

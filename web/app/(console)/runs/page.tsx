"use client";
import { GitCompareArrows, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { EmptyState, ErrorNote, PageHeader, SkeletonRows } from "@/components/page-header";
import { StatusPill } from "@/components/status-pill";
import { Stagger, StaggerItem } from "@/components/motion";
import { useAuth } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import { useRuns } from "@/lib/hooks";
import type { RunStatus } from "@/lib/types";

const FILTERS: (RunStatus | "all")[] = ["all", "running", "paused", "complete", "failed"];

export default function RunsPage() {
  const { role } = useAuth();
  const runs = useRuns();
  const [filter, setFilter] = useState<RunStatus | "all">("all");
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const rows = (runs.data ?? []).filter(
    (r) => (filter === "all" || r.status === filter) && r.run_id.toLowerCase().includes(q.toLowerCase()),
  );
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-2)));

  return (
    <>
      <PageHeader
        eyebrow="Audits"
        title="Runs"
        description="Every audit is a signed ledger. Open a run to see its scores, clauses and evidence."
        actions={
          <>
            {picked.length === 2 && (
              <Link href={`/runs/compare?a=${picked[0]}&b=${picked[1]}`} className="inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-card px-4 text-sm font-medium hover:bg-muted">
                <GitCompareArrows className="size-4" /> Compare
              </Link>
            )}
            {role !== "viewer" && (
              <Link href="/runs/new" className="glow inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90">
                <Plus className="size-4" /> New audit
              </Link>
            )}
          </>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input aria-label="Search runs" placeholder="Search runs" value={q} onChange={(e) => setQ(e.target.value)} className="h-10 w-56 rounded-xl border border-input bg-background pl-9 pr-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/40" />
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by status">
          {FILTERS.map((f) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${filter === f ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}>
              {f}
            </button>
          ))}
        </div>
        {picked.length > 0 && <span className="text-xs text-muted-foreground">{picked.length}/2 selected for comparison</span>}
      </div>
      <ErrorNote error={runs.error} />
      {runs.isLoading && <SkeletonRows rows={5} />}
      {runs.data && rows.length === 0 && (
        <EmptyState title={runs.data.length === 0 ? "No runs yet" : "No runs match"}>
          {runs.data.length === 0 ? "Start an audit to see it here." : "Try another filter or search."}
        </EmptyState>
      )}
      {rows.length > 0 && (
        <Stagger className="space-y-2">
          {rows.map((r) => (
            <StaggerItem key={r.run_id}>
              <div className="hover-lift grid grid-cols-[auto_1fr_auto] items-center gap-4 rounded-2xl border border-border bg-card px-4 py-3 sm:grid-cols-[auto_1.4fr_0.6fr_0.8fr_auto]">
                <input type="checkbox" aria-label={`Select ${r.run_id} to compare`} checked={picked.includes(r.run_id)} onChange={() => toggle(r.run_id)} className="size-4 accent-[var(--primary)]" disabled={r.status !== "complete"} />
                <Link className="min-w-0 truncate font-mono text-sm font-medium underline-offset-4 hover:underline" href={r.status === "complete" ? `/runs/${r.run_id}` : `/runs/${r.run_id}/live`}>{r.run_id}</Link>
                <span className="hidden text-sm text-muted-foreground sm:block">{r.planner}</span>
                <span className="hidden text-sm text-muted-foreground sm:block">{fmtDate(r.created_at)} · {r.created_by}</span>
                <StatusPill status={r.status} />
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </>
  );
}

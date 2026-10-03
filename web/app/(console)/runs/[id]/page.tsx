"use client";
import { ListFilter } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { DimensionChart } from "@/components/dimension-chart";
import { Stagger, StaggerItem } from "@/components/motion";
import { OutcomeBadge } from "@/components/outcome-badge";
import { EmptyState, ErrorNote, SkeletonRows } from "@/components/page-header";
import { RunFrame } from "@/components/run-frame";
import { ScoreCards } from "@/components/score-cards";
import { useDecisions, useFindings, useScores } from "@/lib/hooks";

const BAD = new Set(["block", "fail", "abstain", "waive"]);

export default function OverviewPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RunFrame id={id} active="Overview">
      <Overview id={id} />
    </RunFrame>
  );
}

function Overview({ id }: { id: string }) {
  const scores = useScores(id);
  const decisions = useDecisions(id);
  const findings = useFindings(id);
  if (scores.isLoading || decisions.isLoading) return <SkeletonRows rows={5} />;
  const problems = (decisions.data ?? []).filter((d) => BAD.has(d.outcome));
  return (
    <div className="space-y-8">
      <ErrorNote error={scores.error ?? decisions.error} />
      {scores.data && <ScoreCards scores={scores.data} />}
      {scores.data && (
        <section className="rounded-3xl border border-border bg-card p-5">
          <h2 className="mb-2 font-semibold">Adequacy by dimension</h2>
          <DimensionChart dimensions={scores.data.dimensions} />
        </section>
      )}
      <section>
        <h2 className="mb-3 flex items-center gap-2 font-semibold">
          Controls needing attention <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{problems.length}</span>
        </h2>
        {problems.length === 0 ? (
          <EmptyState title="Nothing needs attention">Every applicable control passed.</EmptyState>
        ) : (
          <Stagger className="grid gap-2 lg:grid-cols-2">
            {problems.map((d) => (
              <StaggerItem key={d.clause_id}>
                <Link href={`/runs/${id}/clauses?control=${d.clause_id}`} className="hover-lift flex items-start gap-3 rounded-2xl border border-border bg-card p-4">
                  <OutcomeBadge outcome={d.outcome} />
                  <span className="min-w-0">
                    <span className="block font-mono text-sm font-medium">{d.clause_id}</span>
                    <span className="block truncate text-sm text-muted-foreground">{d.rationale}</span>
                  </span>
                </Link>
              </StaggerItem>
            ))}
          </Stagger>
        )}
      </section>
      <section>
        <h2 className="mb-3 flex items-center gap-2 font-semibold">
          Agent findings <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{findings.data?.length ?? 0}</span>
        </h2>
        {(findings.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No agent findings in this run (static audits produce measurements and decisions only).</p>
        ) : (
          <ul className="space-y-2">
            {(findings.data ?? []).map((f) => (
              <li key={f.id}>
                <Link className="flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-card p-4 text-sm hover:bg-muted/40" href={`/runs/${id}/findings/${f.id}`}>
                  <ListFilter className="size-4 text-brand" aria-hidden />
                  <span className="font-mono">{f.id}</span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{f.severity}</span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{f.status}</span>
                  <span className="text-muted-foreground">{f.claim}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

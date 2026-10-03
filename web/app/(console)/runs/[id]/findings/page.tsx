"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { EmptyState, ErrorNote, SkeletonRows } from "@/components/page-header";
import { RunFrame } from "@/components/run-frame";
import { useFindings } from "@/lib/hooks";

export default function FindingsPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RunFrame id={id} active="Findings">
      <List id={id} />
    </RunFrame>
  );
}

function List({ id }: { id: string }) {
  const findings = useFindings(id);
  if (findings.isLoading) return <SkeletonRows />;
  if (findings.error) return <ErrorNote error={findings.error} />;
  if (!findings.data?.length) return <EmptyState title="No findings">Agent audits record findings; static audits record measurements and decisions only.</EmptyState>;
  return (
    <ul className="space-y-3">
      {findings.data.map((f) => (
        <li key={f.id}>
          <Link href={`/runs/${id}/findings/${f.id}`} className="hover-lift block rounded-2xl border border-border bg-card p-4">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-mono text-sm font-medium">{f.id}</span>
              <span className="rounded-full bg-muted px-2 py-0.5">{f.severity}</span>
              <span className="rounded-full bg-muted px-2 py-0.5">{f.status}</span>
              <span className="text-muted-foreground">{f.clause_ids.join(", ")}</span>
            </div>
            <p className="mt-2 text-sm">{f.claim}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

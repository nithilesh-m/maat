"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { EvidenceRecordCard } from "@/components/evidence-record";
import { OutcomeBadge } from "@/components/outcome-badge";
import { EmptyState, ErrorNote, SkeletonRows } from "@/components/page-header";
import { RunFrame } from "@/components/run-frame";
import { useDecisions, useFindings, useRecord } from "@/lib/hooks";

export default function FindingDetailPage() {
  const { id, fid } = useParams<{ id: string; fid: string }>();
  return (
    <RunFrame id={id} active="Findings">
      <Detail id={id} fid={fid} />
    </RunFrame>
  );
}

function Cited({ runId, recordId }: { runId: string; recordId: string }) {
  const rec = useRecord(runId, recordId);
  if (rec.isLoading) return <div className="skeleton h-32 rounded-2xl" />;
  if (rec.error || !rec.data) return <ErrorNote error={rec.error ?? new Error("record not found")} />;
  return <EvidenceRecordCard runId={runId} record={rec.data} />;
}

function Detail({ id, fid }: { id: string; fid: string }) {
  const findings = useFindings(id);
  const decisions = useDecisions(id);
  if (findings.isLoading) return <SkeletonRows />;
  const f = findings.data?.find((x) => x.id === fid);
  if (!f) return <EmptyState title="Finding not found"><Link className="underline" href={`/runs/${id}/findings`}>Back to findings</Link></EmptyState>;
  const mine = (decisions.data ?? []).filter((d) => f.clause_ids.includes(d.clause_id));
  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-border bg-card p-6">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-muted px-2 py-0.5">{f.severity}</span>
          <span className="rounded-full bg-muted px-2 py-0.5">{f.status}</span>
          <span className="rounded-full bg-muted px-2 py-0.5">{f.agent} agent</span>
        </div>
        <p className="mt-3 text-lg">{f.claim}</p>
        {f.dispute_reason && <p className="mt-2 text-sm text-warning">Disputed: {f.dispute_reason}</p>}
        <p className="mt-3 text-sm text-muted-foreground">Clauses: {f.clause_ids.map((c) => <Link key={c} className="mr-2 font-mono underline" href={`/runs/${id}/clauses?control=${c}`}>{c}</Link>)}</p>
      </section>
      {mine.map((d) => (
        <section key={d.clause_id} className="rounded-3xl border border-border bg-card p-6">
          <div className="flex items-center gap-3"><h3 className="font-mono font-semibold">{d.clause_id}</h3><OutcomeBadge outcome={d.outcome} /><span className="text-xs text-muted-foreground">via {d.method}</span></div>
          <p className="mt-2 text-sm text-muted-foreground">{d.rationale}</p>
          {d.method === "judge_panel" && (
            <div className="mt-3 overflow-x-auto rounded-xl border border-border">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/50 text-xs text-muted-foreground"><tr><th className="px-3 py-2">Judge</th><th className="px-3 py-2">Label</th><th className="px-3 py-2">Confidence</th><th className="px-3 py-2">Cited</th></tr></thead>
                <tbody className="divide-y divide-border">{d.judges.map((j, i) => <tr key={i}><td className="px-3 py-2">{j.model}</td><td className="px-3 py-2 font-mono">{j.label}</td><td className="px-3 py-2 tabular-nums">{j.confidence.toFixed(2)}</td><td className="px-3 py-2">{j.cited.join(", ")}</td></tr>)}</tbody>
              </table>
              {d.agreement != null && <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">Agreement {d.agreement.toFixed(2)}</p>}
            </div>
          )}
        </section>
      ))}
      <section className="space-y-3">
        <h2 className="font-semibold">Cited evidence</h2>
        {f.evidence_ids.map((rid) => <Cited key={rid} runId={id} recordId={rid} />)}
      </section>
    </div>
  );
}

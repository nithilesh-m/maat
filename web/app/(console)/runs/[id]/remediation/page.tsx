"use client";
import { FlaskConical, Hammer } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { DeltaTable } from "@/components/delta-table";
import { EmptyState, ErrorNote, SkeletonRows } from "@/components/page-header";
import { RunFrame } from "@/components/run-frame";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth";
import { fmtScore } from "@/lib/format";
import { useApplyMitigations, useChildren, useDelta, useMitigations } from "@/lib/hooks";

export default function RemediationPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RunFrame id={id} active="Remediation">
      <Body id={id} />
    </RunFrame>
  );
}

function ChildDelta({ id, child }: { id: string; child: string }) {
  const delta = useDelta(id, child);
  if (delta.isLoading) return <SkeletonRows rows={2} />;
  if (delta.error || !delta.data) return <ErrorNote error={delta.error} />;
  const s = delta.data.summary;
  const num = (k: string) => (typeof s[k] === "number" ? (s[k] as number) : null);
  const util = (k: string) => {
    const v = s[k];
    return v && typeof v === "object" ? (v as Record<string, number>) : null;
  };
  const before = util("utility_before");
  const after = util("utility_after");
  return (
    <section className="space-y-3 rounded-3xl border border-border bg-card p-5">
      <header className="flex flex-wrap items-center gap-3">
        <FlaskConical className="size-5 text-brand" aria-hidden />
        <h3 className="font-mono text-sm font-semibold">{child}</h3>
        <span className="text-sm text-muted-foreground">
          AS {fmtScore(num("AS_before"))} → {fmtScore(num("AS_after"))} (Δ {fmtScore(num("delta_AS"))})
        </span>
        {before && after && (
          <span className="text-sm text-muted-foreground">
            utility {Object.entries(before)[0]?.[0]} {fmtScore(Object.values(before)[0])} → {fmtScore(Object.values(after)[0])}
          </span>
        )}
      </header>
      <DeltaTable rows={delta.data.rows} />
    </section>
  );
}

function Body({ id }: { id: string }) {
  const { role } = useAuth();
  const plans = useMitigations(id);
  const children = useChildren(id);
  const apply = useApplyMitigations(id);
  const [chosen, setChosen] = useState<string[]>([]);
  const [confirm, setConfirm] = useState(false);
  const ids = [...new Set((plans.data?.plans ?? []).map((p) => p.mitigation_id))];
  const picked = chosen.length ? chosen : ids;

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h2 className="font-semibold">Ranked mitigations</h2>
        <ErrorNote error={plans.error} />
        {plans.isLoading ? (
          <SkeletonRows rows={3} />
        ) : !plans.data?.plans.length ? (
          <EmptyState title="No automatic mitigation applies">Failed controls here need manual follow-up.</EmptyState>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-border bg-card">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                <tr><th className="px-4 py-3" /><th className="px-4 py-3 font-medium">Control</th><th className="px-4 py-3 font-medium">Mitigation</th><th className="px-4 py-3 font-medium">Rationale</th><th className="px-4 py-3 font-medium">Severity</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {plans.data.plans.map((p) => (
                  <tr key={`${p.control_id}-${p.mitigation_id}`}>
                    <td className="px-4 py-3"><input type="checkbox" aria-label={`Select ${p.mitigation_id}`} className="size-4 accent-[var(--primary)]" checked={picked.includes(p.mitigation_id)} onChange={(e) => setChosen(e.target.checked ? [...new Set([...picked, p.mitigation_id])] : picked.filter((x) => x !== p.mitigation_id))} /></td>
                    <td className="px-4 py-3 font-mono text-[13px]">{p.control_id}</td>
                    <td className="px-4 py-3 font-medium">{p.mitigation_id}</td>
                    <td className="px-4 py-3 text-muted-foreground">{p.rationale}</td>
                    <td className="px-4 py-3 tabular-nums">{p.severity_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {plans.data && plans.data.manual.length > 0 && (
          <p className="text-sm text-muted-foreground">Manual follow-up: <span className="font-mono">{plans.data.manual.join(", ")}</span></p>
        )}
        <ErrorNote error={apply.error} />
        {apply.isSuccess && <p className="text-sm text-success">Re-test started. The child run appears below when it finishes.</p>}
        {!!plans.data?.plans.length && (
          <div className="flex items-center gap-3">
            <button type="button" disabled={role !== "admin" || apply.isPending} onClick={() => setConfirm(true)} className="glow inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50">
              <Hammer className="size-4" /> Apply in sandbox
            </button>
            {role !== "admin" && <span className="text-xs text-muted-foreground">Admin role required.</span>}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">Re-test results</h2>
        {children.isLoading ? <SkeletonRows rows={2} /> : !children.data?.length ? (
          <EmptyState title="No re-tests yet">Applying mitigations creates a child run with a before and after comparison.</EmptyState>
        ) : (
          children.data.map((c) => <ChildDelta key={c} id={id} child={c} />)
        )}
        <p className="text-xs text-muted-foreground">Back to <Link className="underline" href={`/runs/${id}`}>overview</Link>.</p>
      </section>

      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apply mitigations in the sandbox?</DialogTitle>
            <DialogDescription>MAAT applies {picked.join(", ") || "the selected mitigations"} to a sandboxed snapshot, never to the live system, then re-tests on held-out probes.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm hover:bg-muted" onClick={() => setConfirm(false)}>Cancel</button>
            <button type="button" className="h-9 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground" onClick={async () => { setConfirm(false); await apply.mutateAsync(picked).catch(() => undefined); }}>Apply</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

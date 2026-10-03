"use client";
import { ShieldPlus } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { OutcomeBadge } from "@/components/outcome-badge";
import { EmptyState, ErrorNote, SkeletonRows } from "@/components/page-header";
import { RunFrame } from "@/components/run-frame";
import { WaiverForm } from "@/components/waiver-form";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth";
import { filterRows } from "@/lib/filters";
import { fmtScore, shortHash } from "@/lib/format";
import { useScores, useView } from "@/lib/hooks";
import type { GateOutcome } from "@/lib/types";

const OUTCOMES: (GateOutcome | "")[] = ["", "pass", "block", "fail", "waive", "abstain", "not_applicable"];
const sel = "h-9 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/40";

export default function ClausesPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RunFrame id={id} active="Clauses">
      <Suspense fallback={<SkeletonRows />}>
        <Matrix id={id} />
      </Suspense>
    </RunFrame>
  );
}

function Matrix({ id }: { id: string }) {
  const qs = useSearchParams();
  const { role } = useAuth();
  const scores = useScores(id);
  const regimes = Object.keys(scores.data?.regimes ?? { EU: 0 });
  const [regime, setRegime] = useState("EU");
  const [outcome, setOutcome] = useState<GateOutcome | "">("");
  const [control, setControl] = useState(qs.get("control") ?? "");
  const [waiving, setWaiving] = useState<string | null>(null);
  const view = useView(id, regime);
  const rows = filterRows(view.data?.rows ?? [], { outcome, control });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4 rounded-2xl border border-border bg-card p-4">
        <label className="space-y-1 text-xs font-medium text-muted-foreground">Regime
          <select className={`${sel} block text-foreground`} value={regime} onChange={(e) => setRegime(e.target.value)}>{regimes.map((r) => <option key={r}>{r}</option>)}</select>
        </label>
        <label className="space-y-1 text-xs font-medium text-muted-foreground">Outcome
          <select className={`${sel} block text-foreground`} value={outcome} onChange={(e) => setOutcome(e.target.value as GateOutcome | "")}>{OUTCOMES.map((o) => <option key={o} value={o}>{o || "any"}</option>)}</select>
        </label>
        <label className="space-y-1 text-xs font-medium text-muted-foreground">Control
          <input className={`${sel} block w-40 text-foreground`} value={control} onChange={(e) => setControl(e.target.value)} />
        </label>
        {view.data && (
          <dl className="ml-auto flex items-end gap-8 text-sm">
            {([["CC", view.data.cc], ["AS", view.data.as], ["MER", view.data.mer]] as const).map(([k, v]) => (
              <div key={k}><dt className="text-xs text-muted-foreground">{k}</dt><dd className="font-semibold tabular-nums">{fmtScore(v)}</dd></div>
            ))}
          </dl>
        )}
      </div>
      <ErrorNote error={view.error} />
      {view.isLoading ? (
        <SkeletonRows rows={6} />
      ) : rows.length === 0 ? (
        <EmptyState title="No clauses match">Change the regime or clear a filter.</EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border bg-card">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
              <tr><th className="px-4 py-3 font-medium">Regime clause</th><th className="px-4 py-3 font-medium">Control</th><th className="px-4 py-3 font-medium">Outcome</th><th className="px-4 py-3 font-medium">a_c</th><th className="px-4 py-3 font-medium">Evidence</th><th className="px-4 py-3"><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((r) => (
                <tr key={`${r.regime_clause}-${r.control_id}`} className="transition hover:bg-muted/40">
                  <td className="px-4 py-3">{r.regime_clause}</td>
                  <td className="px-4 py-3 font-mono text-[13px]">{r.control_id}</td>
                  <td className="px-4 py-3"><OutcomeBadge outcome={r.outcome} /></td>
                  <td className="px-4 py-3 tabular-nums">{r.adequacy}</td>
                  <td className="px-4 py-3">{r.evidence.map((e) => <Link key={e.record_id} className="mr-2 font-mono text-xs underline-offset-4 hover:underline" href={`/runs/${id}/records/${e.record_id}`}>{shortHash(e.hash)}</Link>)}</td>
                  <td className="px-4 py-3 text-right">
                    {r.outcome === "block" && role !== "viewer" && (
                      <button type="button" onClick={() => setWaiving(r.control_id)} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-2.5 text-xs font-medium hover:bg-muted">
                        <ShieldPlus className="size-3.5" /> Add waiver
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Dialog open={!!waiving} onOpenChange={(o) => !o && setWaiving(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add waiver for {waiving}</DialogTitle>
            <DialogDescription>A waiver is time-limited, owned and signed. It cannot apply to non-waivable controls at your risk tier.</DialogDescription>
          </DialogHeader>
          {waiving && <WaiverForm runId={id} clauseId={waiving} onDone={() => setWaiving(null)} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}

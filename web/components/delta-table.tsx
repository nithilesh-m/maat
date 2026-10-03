import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { OutcomeBadge } from "@/components/outcome-badge";
import { EmptyState } from "@/components/page-header";
import type { DeltaRow } from "@/lib/types";

export function DeltaTable({ rows }: { rows: DeltaRow[] }) {
  if (rows.length === 0) return <EmptyState title="No clauses changed">This re-test has no clause rows to compare.</EmptyState>;
  return (
    <div className="overflow-x-auto rounded-2xl border border-border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-4 py-3 font-medium">Control</th>
            <th className="px-4 py-3 font-medium">Clause</th>
            <th className="px-4 py-3 font-medium">Before</th>
            <th className="px-4 py-3 font-medium">After</th>
            <th className="px-4 py-3 font-medium">a_c</th>
            <th className="px-4 py-3"><span className="sr-only">Change</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => {
            const d = r.after_a - (r.before_a ?? 0);
            return (
              <tr key={`${r.control_id}-${r.regime_clause}`} className="transition hover:bg-muted/40">
                <td className="px-4 py-3 font-mono text-[13px]">{r.control_id}</td>
                <td className="px-4 py-3 text-muted-foreground">{r.regime_clause}</td>
                <td className="px-4 py-3">{r.before_outcome ? <OutcomeBadge outcome={r.before_outcome} /> : "–"}</td>
                <td className="px-4 py-3"><OutcomeBadge outcome={r.after_outcome} /></td>
                <td className="px-4 py-3 tabular-nums">{r.before_a ?? "–"} → {r.after_a}</td>
                <td className="px-4 py-3">
                  {d > 0 ? (
                    <span aria-label="improved" className="inline-flex items-center gap-1 text-success"><ArrowUpRight className="size-4" aria-hidden />▲</span>
                  ) : d < 0 ? (
                    <span aria-label="regressed" className="inline-flex items-center gap-1 text-destructive"><ArrowDownRight className="size-4" aria-hidden />▼</span>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

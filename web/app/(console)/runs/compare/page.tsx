"use client";
import { ArrowRight } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { OutcomeBadge } from "@/components/outcome-badge";
import { EmptyState, ErrorNote, PageHeader, SkeletonRows } from "@/components/page-header";
import { useDecisions, useRuns } from "@/lib/hooks";

export default function ComparePage() {
  return (
    <Suspense fallback={<SkeletonRows />}>
      <Compare />
    </Suspense>
  );
}

function Compare() {
  const qs = useSearchParams();
  const router = useRouter();
  const a = qs.get("a") ?? "";
  const b = qs.get("b") ?? "";
  const runs = useRuns();
  const da = useDecisions(a, !!a);
  const db = useDecisions(b, !!b);
  const complete = (runs.data ?? []).filter((r) => r.status === "complete");

  const pick = (which: "a" | "b") => (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = new URLSearchParams({ a, b, [which]: e.target.value });
    router.replace(`/runs/compare?${next.toString()}`);
  };

  const ids = [...new Set([...(da.data ?? []), ...(db.data ?? [])].map((d) => d.clause_id))].sort();
  const get = (list: typeof da.data, id: string) => list?.find((d) => d.clause_id === id);

  return (
    <>
      <PageHeader eyebrow="Compare" title="Compare runs" description="Decisions side by side. Changed outcomes are highlighted. Values come straight from the API." />
      <div className="mb-5 grid gap-3 sm:grid-cols-2">
        {([["a", a], ["b", b]] as const).map(([w, v]) => (
          <label key={w} className="space-y-1 text-xs font-medium text-muted-foreground">Run {w.toUpperCase()}
            <select aria-label={`Run ${w.toUpperCase()}`} value={v} onChange={pick(w)} className="block h-10 w-full rounded-xl border border-input bg-background px-3 text-sm text-foreground">
              <option value="">Choose a run</option>
              {complete.map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id}</option>)}
            </select>
          </label>
        ))}
      </div>
      <ErrorNote error={da.error ?? db.error} />
      {!a || !b ? (
        <EmptyState title="Pick two completed runs">Select them above, or tick two runs on the Runs page.</EmptyState>
      ) : da.isLoading || db.isLoading ? (
        <SkeletonRows rows={5} />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border bg-card">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground"><tr><th className="px-4 py-3">Control</th><th className="px-4 py-3">A</th><th className="px-4 py-3" /><th className="px-4 py-3">B</th></tr></thead>
            <tbody className="divide-y divide-border">
              {ids.map((id) => {
                const x = get(da.data, id);
                const y = get(db.data, id);
                const changed = x?.outcome !== y?.outcome;
                return (
                  <tr key={id} className={changed ? "bg-warning/8" : ""} data-changed={changed}>
                    <td className="px-4 py-3 font-mono text-[13px]">{id}</td>
                    <td className="px-4 py-3">{x ? <OutcomeBadge outcome={x.outcome} /> : "–"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{changed && <ArrowRight className="size-4" aria-label="changed" />}</td>
                    <td className="px-4 py-3">{y ? <OutcomeBadge outcome={y.outcome} /> : "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

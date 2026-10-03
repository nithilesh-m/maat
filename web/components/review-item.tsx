"use client";
import { Gavel } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorNote } from "@/components/page-header";
import { useAuth } from "@/lib/auth";
import { type QueueItem, useReview } from "@/lib/hooks";

const LABELS = [
  ["S", "Satisfied"],
  ["P", "Partial"],
  ["N", "Not satisfied"],
  ["NA", "Not applicable"],
] as const;

export function ReviewItem({ item }: { item: QueueItem }) {
  const { role } = useAuth();
  const review = useReview(item.run_id);
  const [label, setLabel] = useState("");
  const [why, setWhy] = useState("");
  return (
    <article className="rounded-3xl border border-border bg-card p-5" aria-label={`Review ${item.clause_id}`}>
      <header className="flex flex-wrap items-center gap-2">
        <span className="grid size-9 place-items-center rounded-xl bg-warning/15 text-warning"><Gavel className="size-4" aria-hidden /></span>
        <h3 className="font-mono text-sm font-semibold">{item.clause_id}</h3>
        <Link className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline" href={`/runs/${item.run_id}`}>{item.run_id}</Link>
      </header>
      <p className="mt-3 text-sm text-muted-foreground">{item.rationale}</p>
      {item.judges.length > 0 && (
        <div className="mt-3 overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr><th className="px-3 py-2 font-medium">Judge</th><th className="px-3 py-2 font-medium">Label</th><th className="px-3 py-2 font-medium">Conf.</th><th className="px-3 py-2 font-medium">Cited</th></tr>
            </thead>
            <tbody className="divide-y divide-border">
              {item.judges.map((j, i) => (
                <tr key={`${j.model}-${i}`}>
                  <td className="px-3 py-2">{j.model}</td>
                  <td className="px-3 py-2 font-mono">{j.label}</td>
                  <td className="px-3 py-2 tabular-nums">{j.confidence.toFixed(2)}</td>
                  <td className="px-3 py-2">{j.cited.map((c) => <Link key={c} className="mr-2 font-mono text-xs underline" href={`/runs/${item.run_id}/records/${c}`}>{c.slice(-8)}</Link>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {role !== "viewer" ? (
        <form
          className="mt-4 space-y-3"
          onSubmit={async (e) => {
            e.preventDefault();
            await review.mutateAsync({ clause_id: item.clause_id, label, rationale: why });
          }}
        >
          <fieldset className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <legend className="sr-only">Decision</legend>
            {LABELS.map(([v, t]) => (
              <label key={v} className={`flex cursor-pointer items-center justify-center rounded-xl border px-3 py-2 text-sm transition has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50 ${label === v ? "border-primary bg-primary/10 font-medium text-primary" : "border-border hover:bg-muted"}`}>
                <input type="radio" className="sr-only" name={`l-${item.run_id}-${item.clause_id}`} value={v} checked={label === v} onChange={() => setLabel(v)} />
                {t}
              </label>
            ))}
          </fieldset>
          <textarea aria-label="Rationale" placeholder="Rationale (required)" value={why} onChange={(e) => setWhy(e.target.value)} rows={2} className="w-full rounded-xl border border-input bg-background p-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/40" />
          <ErrorNote error={review.error} />
          <button type="submit" disabled={!label || !why.trim() || review.isPending} className="h-10 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50">
            {review.isPending ? "Recording…" : "Record decision"}
          </button>
        </form>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">Viewers can read the queue; reviewers record decisions.</p>
      )}
    </article>
  );
}

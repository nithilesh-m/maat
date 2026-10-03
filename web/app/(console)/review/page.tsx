"use client";
import { PartyPopper } from "lucide-react";
import { EmptyState, ErrorNote, PageHeader, SkeletonRows } from "@/components/page-header";
import { Stagger, StaggerItem } from "@/components/motion";
import { ReviewItem } from "@/components/review-item";
import { type QueueItem, useReviewQueue, useWaivers } from "@/lib/hooks";
import { fmtDate } from "@/lib/format";

export default function ReviewPage() {
  const queue = useReviewQueue();
  const waivers = useWaivers();
  const groups = (queue.data ?? []).reduce<Record<string, QueueItem[]>>((acc, i) => {
    (acc[i.run_id] ??= []).push(i);
    return acc;
  }, {});
  return (
    <>
      <PageHeader eyebrow="Human in the loop" title="Review queue" description="Controls the judge panel could not decide. A reviewer's verdict is signed and sealed as a new bundle revision." />
      <ErrorNote error={queue.error} />
      {queue.isLoading && <SkeletonRows rows={3} />}
      {queue.data && queue.data.length === 0 && (
        <EmptyState icon={<PartyPopper className="size-5" />} title="Nothing awaiting review">Abstained controls from sealed runs will appear here.</EmptyState>
      )}
      <div className="space-y-8">
        {Object.entries(groups).map(([run, items]) => (
          <section key={run}>
            <h2 className="mb-3 font-mono text-sm font-semibold text-muted-foreground">{run}</h2>
            <Stagger className="space-y-3">
              {items.map((it) => (
                <StaggerItem key={`${it.run_id}-${it.clause_id}`}><ReviewItem item={it} /></StaggerItem>
              ))}
            </Stagger>
          </section>
        ))}
      </div>
      {!!waivers.data?.length && (
        <section className="mt-12">
          <h2 className="mb-3 font-semibold">Active waivers</h2>
          <div className="overflow-x-auto rounded-2xl border border-border bg-card">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground"><tr><th className="px-4 py-3">Run</th><th className="px-4 py-3">Control</th><th className="px-4 py-3">Owner</th><th className="px-4 py-3">Scope</th><th className="px-4 py-3">Expiry</th></tr></thead>
              <tbody className="divide-y divide-border">
                {waivers.data.map((w) => (
                  <tr key={w.record_id}><td className="px-4 py-3 font-mono text-xs">{w.run_id}</td><td className="px-4 py-3 font-mono text-[13px]">{w.waiver.clause_id}</td><td className="px-4 py-3">{w.waiver.owner}</td><td className="px-4 py-3">{w.waiver.scope}</td><td className="px-4 py-3">{fmtDate(w.waiver.expiry)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

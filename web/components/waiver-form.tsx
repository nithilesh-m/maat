"use client";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { ErrorNote } from "@/components/page-header";
import { useWaiver } from "@/lib/hooks";
import { validateWaiver } from "@/lib/waiver";

const field =
  "h-10 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none transition focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40";

const stamp = () => new Date().toISOString().slice(0, 10).replaceAll("-", "");

export function WaiverForm({ runId, clauseId, onDone }: { runId: string; clauseId: string; onDone?: () => void }) {
  const waiver = useWaiver(runId);
  const [id, setId] = useState(`W-${clauseId}-${stamp()}`);
  const [owner, setOwner] = useState("");
  const [scope, setScope] = useState("");
  const [expiry, setExpiry] = useState("");
  const [comps, setComps] = useState<string[]>([""]);
  const [errs, setErrs] = useState<string[]>([]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const iso = expiry ? new Date(`${expiry}T23:59:59Z`).toISOString() : "";
    const found = validateWaiver({ id, clause_id: clauseId, owner, scope, expiry: iso, compensations: comps });
    setErrs(found);
    if (found.length) return;
    await waiver.mutateAsync({ id, clause_id: clauseId, owner, scope, expiry: iso, compensations: comps.filter((c) => c.trim()) });
    onDone?.();
  };

  return (
    <form onSubmit={submit} className="space-y-3" aria-label={`Waiver for ${clauseId}`}>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1.5 text-sm font-medium">Waiver id<input className={field} value={id} onChange={(e) => setId(e.target.value)} /></label>
        <label className="space-y-1.5 text-sm font-medium">Owner<input className={field} value={owner} onChange={(e) => setOwner(e.target.value)} /></label>
        <label className="space-y-1.5 text-sm font-medium">Scope<input className={field} value={scope} onChange={(e) => setScope(e.target.value)} /></label>
        <label className="space-y-1.5 text-sm font-medium">Expiry (max 90 days)<input type="date" className={field} value={expiry} onChange={(e) => setExpiry(e.target.value)} /></label>
      </div>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Compensating measures</legend>
        {comps.map((c, i) => (
          <div key={i} className="flex gap-2">
            <input aria-label={`Compensating measure ${i + 1}`} className={field} value={c} onChange={(e) => setComps(comps.map((x, j) => (j === i ? e.target.value : x)))} />
            <button type="button" aria-label={`Remove measure ${i + 1}`} disabled={comps.length === 1} onClick={() => setComps(comps.filter((_, j) => j !== i))} className="grid size-10 shrink-0 place-items-center rounded-xl border border-border hover:bg-muted disabled:opacity-40">
              <Trash2 className="size-4" />
            </button>
          </div>
        ))}
        <button type="button" aria-label="Add compensating measure" onClick={() => setComps([...comps, ""])} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-3 text-xs font-medium hover:bg-muted">
          <Plus className="size-3.5" /> Add measure
        </button>
      </fieldset>
      {errs.length > 0 && (
        <ul role="alert" className="list-disc space-y-0.5 rounded-xl bg-destructive/10 py-2 pl-7 pr-3 text-sm text-destructive">
          {errs.map((e) => <li key={e}>{e}</li>)}
        </ul>
      )}
      <ErrorNote error={waiver.error} />
      <button type="submit" disabled={waiver.isPending} className="h-10 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50">
        {waiver.isPending ? "Saving…" : "Add waiver"}
      </button>
    </form>
  );
}

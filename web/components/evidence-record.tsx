"use client";
import { Download, Eye, Fingerprint, TriangleAlert } from "lucide-react";
import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiBase } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { shortHash } from "@/lib/format";
import type { ArtifactRef, EvidenceRecord } from "@/lib/types";

async function download(runId: string, a: ArtifactRef, token: string, sensitive: boolean) {
  const r = await fetch(
    `${apiBase()}/api/v1/artifacts/${runId}/${a.sha256}${sensitive ? "?include_sensitive=true" : ""}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: r.statusText }))).detail);
  const url = URL.createObjectURL(await r.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = a.uri.split("/").pop() ?? "artifact";
  link.click();
  URL.revokeObjectURL(url);
}

const btn =
  "inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-background px-3 text-xs font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50";

export function EvidenceRecordCard({ runId, record }: { runId: string; record: EvidenceRecord }) {
  const { token, role } = useAuth();
  const [pending, setPending] = useState<ArtifactRef | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const metrics = record.result.metrics ?? {};
  const samples = (record.result.samples as unknown[] | undefined) ?? [];
  return (
    <article className="rounded-2xl border border-border bg-card p-5" aria-label={`Evidence record ${record.id}`}>
      <header className="flex flex-wrap items-center gap-2">
        <span className="grid size-8 place-items-center rounded-xl bg-accent text-accent-foreground">
          <Fingerprint className="size-4" aria-hidden />
        </span>
        <h3 className="font-mono text-sm font-medium">{record.tool}</h3>
        <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{record.evidence_type}</span>
        <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{record.agent}</span>
      </header>
      <div className="mt-4 space-y-3 text-sm">
        {record.result.error && (
          <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-destructive">Error: {String(record.result.error)}</p>
        )}
        {Object.keys(metrics).length > 0 && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3">
            {Object.entries(metrics).map(([k, v]) => (
              <div key={k} className="min-w-0">
                <dt className="truncate text-xs text-muted-foreground">{k}</dt>
                <dd className="truncate font-mono text-[13px]">{String(v)}</dd>
              </div>
            ))}
          </dl>
        )}
        {samples.length > 0 && (
          <pre className="max-h-64 overflow-auto rounded-xl bg-muted p-3 font-mono text-xs">{JSON.stringify(samples, null, 2).slice(0, 4000)}</pre>
        )}
        <p className="text-xs text-muted-foreground">
          record <span className="font-mono">{record.id}</span> · <span className="font-mono">{shortHash(record.hash)}</span> · signer{" "}
          <span className="font-mono">{record.signer.slice(0, 10)}…</span>
        </p>
        {record.artifacts.length > 0 && (
          <ul className="space-y-2">
            {record.artifacts.map((a) => (
              <li key={a.sha256} className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-xs">{a.uri.split("/").pop()}</span>
                {a.sensitive ? (
                  <button
                    type="button"
                    className={btn}
                    disabled={role === "viewer"}
                    aria-label={`Reveal sensitive artifact ${a.uri}`}
                    onClick={() => setPending(a)}
                  >
                    <Eye className="size-3.5" aria-hidden /> Reveal (reviewer)
                  </button>
                ) : (
                  <button type="button" className={btn} onClick={() => download(runId, a, token!, false).catch((e) => setErr(e.message))}>
                    <Download className="size-3.5" aria-hidden /> Download
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {err && <p role="alert" className="text-destructive">{err}</p>}
      </div>
      <Dialog open={!!pending} onOpenChange={(o) => !o && setPending(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><TriangleAlert className="size-5 text-warning" /> Reveal sensitive artifact?</DialogTitle>
            <DialogDescription>
              This file may contain red-team prompts, harmful model output or personal data from the system under audit. Only open it if you need it for review.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button type="button" className={btn} onClick={() => setPending(null)}>Cancel</button>
            <button
              type="button"
              className="inline-flex h-8 items-center rounded-lg bg-primary px-3 text-xs font-medium text-primary-foreground"
              onClick={() => {
                const a = pending!;
                setPending(null);
                download(runId, a, token!, true).catch((e) => setErr(e.message));
              }}
            >
              Reveal
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </article>
  );
}

"use client";
import { Download, FileText, ShieldAlert, ShieldCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ErrorNote, SkeletonRows } from "@/components/page-header";
import { RunFrame } from "@/components/run-frame";
import { apiBase } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { useVerify } from "@/lib/hooks";

export default function BundlePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RunFrame id={id} active="Bundle">
      <Body id={id} />
    </RunFrame>
  );
}

interface Header {
  bundle_id: string;
  revision: number;
  previous_bundle_id: string | null;
  signers: string[];
  versions: Record<string, string>;
  tier: string;
  regimes: string[];
}

function decodeHeader(envelope: { payload: string }): Header {
  const stmt = JSON.parse(atob(envelope.payload));
  return stmt.predicate.header as Header;
}

const btn = "inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-card px-4 text-sm font-medium transition hover:bg-muted";

function Body({ id }: { id: string }) {
  const { token } = useAuth();
  const verify = useVerify(id);
  const [header, setHeader] = useState<Header | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const fetchAuth = async (path: string) => {
    const r = await fetch(`${apiBase()}/api/v1/runs/${id}/${path}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: r.statusText }))).detail);
    return r;
  };
  const getBundle = async () => {
    setErr(null);
    try {
      const env = await (await fetchAuth("bundle")).json();
      setHeader(decodeHeader(env));
      const url = URL.createObjectURL(new Blob([JSON.stringify(env, null, 2)], { type: "application/json" }));
      const a = Object.assign(document.createElement("a"), { href: url, download: `${id}.bundle.dsse.json` });
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  const openReport = async () => {
    setErr(null);
    try {
      const url = URL.createObjectURL(await (await fetchAuth("report.html")).blob());
      window.open(url, "_blank", "noopener");
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <div className="space-y-6">
      {verify.isLoading ? (
        <SkeletonRows rows={1} />
      ) : verify.data?.ok ? (
        <div className="flex items-center gap-4 rounded-3xl border border-success/40 bg-success/10 p-5 text-success">
          <ShieldCheck className="size-7" aria-hidden />
          <div><p className="font-semibold">VALID</p><p className="text-sm opacity-90">Hash chain, signatures, artifacts and Merkle root verified ({verify.data.records} records).</p></div>
        </div>
      ) : verify.data ? (
        <div role="alert" className="rounded-3xl border border-destructive/40 bg-destructive/10 p-5 text-destructive">
          <p className="flex items-center gap-2 font-semibold"><ShieldAlert className="size-5" /> INVALID</p>
          <ul className="mt-2 list-disc pl-6 text-sm">{verify.data.problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      ) : null}
      <ErrorNote error={verify.error} />
      <div className="flex flex-wrap gap-3">
        <button type="button" className={btn} onClick={getBundle}><Download className="size-4" /> Download bundle JSON</button>
        <button type="button" className={btn} onClick={openReport}><FileText className="size-4" /> Open report</button>
      </div>
      {err && <p role="alert" className="text-sm text-destructive">{err}</p>}
      {header && (
        <section className="rounded-3xl border border-border bg-card p-5">
          <h2 className="mb-3 font-semibold">Bundle header</h2>
          <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
            <div className="sm:col-span-2"><dt className="text-xs text-muted-foreground">Bundle id</dt><dd className="break-all font-mono text-[13px]">{header.bundle_id}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Revision</dt><dd>{header.revision}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Previous</dt><dd className="break-all font-mono text-[13px]">{header.previous_bundle_id ?? "–"}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Tier</dt><dd>{header.tier}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Regimes</dt><dd>{header.regimes.join(", ")}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs text-muted-foreground">Signers</dt><dd>{header.signers.map((s) => <p key={s} className="break-all font-mono text-[13px]">{s}</p>)}</dd></div>
          </dl>
          <h3 className="mb-2 mt-5 text-sm font-semibold">Versions</h3>
          <dl className="grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
            {Object.entries(header.versions).map(([k, v]) => <div key={k} className="min-w-0"><dt className="truncate text-xs text-muted-foreground">{k}</dt><dd className="truncate font-mono text-[13px]">{v}</dd></div>)}
          </dl>
        </section>
      )}
    </div>
  );
}

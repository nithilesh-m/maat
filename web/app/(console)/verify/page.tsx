"use client";
import { motion } from "framer-motion";
import { FileArchive, Loader2, ShieldAlert, ShieldCheck, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { ErrorNote, PageHeader } from "@/components/page-header";
import { useVerifyUpload } from "@/lib/hooks";

export default function VerifyPage() {
  const verify = useVerifyUpload();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [name, setName] = useState<string | null>(null);
  const run = (f: File | undefined) => {
    if (!f) return;
    setName(f.name);
    verify.mutate(f);
  };
  return (
    <>
      <PageHeader eyebrow="Independent check" title="Verify a bundle" description="Upload a zipped run directory. The server re-checks its hash chain, signatures, artifacts and Merkle root without trusting where it came from." />
      <div
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); run(e.dataTransfer.files[0]); }}
        className={`grid place-items-center rounded-3xl border-2 border-dashed px-6 py-16 text-center transition ${over ? "border-primary bg-primary/8" : "border-border bg-card/50"}`}
      >
        <motion.div animate={over ? { scale: 1.08 } : { scale: 1 }} className="mb-4 grid size-14 place-items-center rounded-2xl bg-accent text-accent-foreground">
          <UploadCloud className="size-7" aria-hidden />
        </motion.div>
        <p className="font-medium">Drop a .zip of a run folder here</p>
        <p className="mt-1 text-sm text-muted-foreground">or</p>
        <label htmlFor="zip" className="mt-3 inline-flex h-10 cursor-pointer items-center gap-2 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90">
          <FileArchive className="size-4" /> Choose file
        </label>
        <input id="zip" ref={input} type="file" accept=".zip" className="sr-only" onChange={(e) => run(e.target.files?.[0])} />
        {name && <p className="mt-3 font-mono text-xs text-muted-foreground">{name}</p>}
      </div>
      <div className="mt-6 space-y-3">
        {verify.isPending && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Verifying…</p>}
        <ErrorNote error={verify.error} />
        {verify.data && (verify.data.ok ? (
          <div className="flex items-center gap-4 rounded-3xl border border-success/40 bg-success/10 p-5 text-success">
            <ShieldCheck className="size-7" aria-hidden />
            <div><p className="font-semibold">VALID</p><p className="text-sm">{verify.data.records} records · <span className="break-all font-mono">{verify.data.bundle_id}</span></p></div>
          </div>
        ) : (
          <div role="alert" className="rounded-3xl border border-destructive/40 bg-destructive/10 p-5 text-destructive">
            <p className="flex items-center gap-2 font-semibold"><ShieldAlert className="size-5" /> INVALID</p>
            <ul className="mt-2 list-disc pl-6 text-sm">{verify.data.problems.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
        ))}
      </div>
    </>
  );
}

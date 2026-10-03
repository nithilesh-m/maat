"use client";
import { FileUp, Rocket } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorNote, PageHeader } from "@/components/page-header";
import { useAuth } from "@/lib/auth";
import { useCreateRun } from "@/lib/hooks";
import { validateProfileYaml } from "@/lib/profile";

const PLANNERS = [
  ["agents", "Agents (LLM)", "Orchestrator and specialist agents plan and run the tools."],
  ["static", "Static (B0)", "A fixed plan runs every applicable tool: no model needed."],
] as const;

export default function NewAuditPage() {
  const { role } = useAuth();
  const router = useRouter();
  const create = useCreateRun();
  const [yamlText, setYaml] = useState("");
  const [planner, setPlanner] = useState<"agents" | "static">("agents");
  const [auto, setAuto] = useState(false);
  const check = yamlText ? validateProfileYaml(yamlText) : null;

  if (role === "viewer")
    return <p className="rounded-2xl border border-border bg-card p-6">Your role (viewer) cannot start audits.</p>;

  return (
    <>
      <PageHeader eyebrow="Audits" title="New audit" description="Describe the system with a profile, choose how to plan the audit, then watch it run." />
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-3">
          <label htmlFor="file" className="flex cursor-pointer items-center gap-3 rounded-2xl border border-dashed border-border bg-card/50 px-4 py-3 text-sm transition hover:border-primary hover:bg-accent/40">
            <FileUp className="size-5 text-brand" aria-hidden />
            <span>Upload <span className="font-mono">system_profile.yaml</span></span>
            <input id="file" type="file" accept=".yaml,.yml" className="sr-only" onChange={async (e) => { const f = e.target.files?.[0]; if (f) setYaml(await f.text()); }} />
          </label>
          <label htmlFor="yaml" className="block text-sm font-medium">Profile YAML</label>
          <textarea id="yaml" rows={18} spellCheck={false} value={yamlText} onChange={(e) => setYaml(e.target.value)} className="w-full rounded-2xl border border-input bg-background p-4 font-mono text-[13px] leading-relaxed outline-none transition focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40" />
          {check && !check.ok && <p role="alert" className="text-sm text-destructive">{check.error}</p>}
          {check?.ok && <p className="text-sm text-success">Profile looks valid. The server checks it again on submit.</p>}
        </div>
        <div className="space-y-5">
          <fieldset className="space-y-2">
            <legend className="mb-1 text-sm font-medium">Planner</legend>
            {PLANNERS.map(([v, t, d]) => (
              <label key={v} className={`flex cursor-pointer gap-3 rounded-2xl border p-4 transition has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50 ${planner === v ? "border-primary bg-primary/8" : "border-border hover:bg-muted/60"}`}>
                <input type="radio" name="planner" className="mt-1 accent-[var(--primary)]" checked={planner === v} onChange={() => setPlanner(v)} />
                <span><span className="block text-sm font-medium">{t}</span><span className="text-xs text-muted-foreground">{d}</span></span>
              </label>
            ))}
          </fieldset>
          <label className="flex items-center gap-3 rounded-2xl border border-border p-4 text-sm">
            <input type="checkbox" className="size-4 accent-[var(--primary)]" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
            Auto-approve tier and ERS
          </label>
          <ErrorNote error={create.error} />
          <button
            type="button"
            disabled={!check?.ok || create.isPending}
            onClick={async () => {
              const r = await create.mutateAsync({ profile_yaml: yamlText, planner, auto_approve: auto });
              router.push(`/runs/${r.run_id}/live`);
            }}
            className="glow inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
          >
            <Rocket className="size-4" /> {create.isPending ? "Starting…" : "Start audit"}
          </button>
        </div>
      </div>
    </>
  );
}

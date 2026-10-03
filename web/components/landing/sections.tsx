"use client";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BadgeCheck,
  Fingerprint,
  GitCompareArrows,
  Gavel,
  Layers,
  LockKeyhole,
  RotateCcw,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { Aurora } from "@/components/landing/aurora";
import { Wordmark } from "@/components/brand/logo";
import { FadeIn, Reveal, Stagger, StaggerItem } from "@/components/motion";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { useAuth } from "@/lib/auth";

const cta =
  "inline-flex h-11 items-center justify-center gap-2 rounded-xl px-5 text-sm font-medium outline-none transition focus-visible:ring-3 focus-visible:ring-ring/50";

export function SiteNav() {
  const { token } = useAuth();
  return (
    <header className="glass sticky top-0 z-40 border-x-0 border-t-0">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" aria-label="MAAT home">
          <Wordmark />
        </Link>
        <nav aria-label="Sections" className="ml-6 hidden items-center gap-6 text-sm text-muted-foreground md:flex">
          {[
            ["#pillars", "Principles"],
            ["#how", "How it works"],
            ["#proof", "Proof"],
            ["#trust", "Trust"],
          ].map(([h, l]) => (
            <a key={h} href={h} className="transition hover:text-foreground">
              {l}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeSwitcher />
          <Link href={token ? "/runs" : "/login"} className={`${cta} h-9 bg-primary text-primary-foreground hover:opacity-90`}>
            {token ? "Open console" : "Sign in"}
          </Link>
        </div>
      </div>
    </header>
  );
}

const CHAIN = [
  { tool: "probe_prompt_injection", agent: "risk", hash: "sha256:7d36a616", note: "asr measured" },
  { tool: "probe_ai_disclosure", agent: "compliance", hash: "sha256:3d20fb7f", note: "disclosure measured" },
  { tool: "check_doc_completeness", agent: "compliance", hash: "sha256:b85c9c05", note: "documents checked" },
  { tool: "gate: VG-SEC-01", agent: "rego", hash: "sha256:0e27ade8", note: "decision recorded" },
];

function EvidenceChain() {
  return (
    <div className="relative mx-auto w-full max-w-md" aria-label="Illustration: a hash-chained evidence ledger">
      <div className="absolute -inset-6 -z-10 rounded-[2rem] bg-gradient-to-br from-brand/25 via-transparent to-brand-2/25 blur-2xl" />
      <div className="glass glow rounded-3xl p-5">
        <div className="mb-4 flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-mono">ledger.sqlite</span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-success/12 px-2.5 py-1 font-medium text-success ring-1 ring-success/30">
            <ShieldCheck className="size-3.5" /> VALID
          </span>
        </div>
        <ol className="relative space-y-3">
          <span className="absolute bottom-6 left-[1.05rem] top-6 w-px bg-gradient-to-b from-brand via-brand-2 to-transparent" aria-hidden />
          {CHAIN.map((r, i) => (
            <motion.li
              key={r.hash}
              initial={{ opacity: 0, x: 18 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 + i * 0.22, duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
              className="relative flex items-center gap-3 rounded-2xl border border-border bg-card/80 px-3 py-2.5"
            >
              <span className="relative z-10 grid size-8 shrink-0 place-items-center rounded-full bg-primary/12 text-primary ring-1 ring-primary/30">
                <Fingerprint className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-[13px]">{r.tool}</span>
                <span className="block text-[11px] text-muted-foreground">
                  {r.agent} · {r.note}
                </span>
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">{r.hash}</span>
            </motion.li>
          ))}
        </ol>
        <p className="mt-4 text-center text-[11px] text-muted-foreground">Illustration · each record signs the hash of the one before it</p>
      </div>
      <div className="absolute -right-4 -top-5 hidden animate-float rounded-2xl border border-border bg-card px-3 py-2 text-xs shadow-lg sm:block">
        <span className="text-muted-foreground">Ed25519</span> <span className="font-mono">signed</span>
      </div>
      <div className="absolute -bottom-5 -left-4 hidden animate-float rounded-2xl border border-border bg-card px-3 py-2 text-xs shadow-lg [animation-delay:-3s] sm:block">
        <span className="text-muted-foreground">RFC 8785</span> <span className="font-mono">canonical</span>
      </div>
    </div>
  );
}

export function Hero() {
  const { token } = useAuth();
  return (
    <section className="relative overflow-hidden">
      <Aurora />
      <div className="mx-auto grid max-w-7xl items-center gap-14 px-4 pb-24 pt-20 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:pt-28">
        <div>
          <FadeIn>
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
              <Sparkles className="size-3.5 text-brand" /> Measured · Signed · Clause-traceable
            </span>
          </FadeIn>
          <FadeIn delay={0.08}>
            <h1 className="mt-6 text-balance text-5xl font-semibold leading-[1.04] tracking-tight sm:text-6xl lg:text-[4.25rem]">
              Audit AI systems with evidence you can <span className="text-gradient">verify</span>.
            </h1>
          </FadeIn>
          <FadeIn delay={0.16}>
            <p className="mt-6 max-w-xl text-pretty text-lg text-muted-foreground">
              MAAT sends agents to test a system with real tools, records every measurement in a signed ledger, and
              lets rules, a judge panel and humans decide each clause. Anyone can re-verify the result.
            </p>
          </FadeIn>
          <FadeIn delay={0.24} className="mt-9 flex flex-wrap items-center gap-3">
            <Link href={token ? "/runs" : "/login"} className={`${cta} glow bg-primary text-primary-foreground hover:opacity-90`}>
              {token ? "Open the console" : "Sign in to the console"} <ArrowRight className="size-4" />
            </Link>
            <a href="#how" className={`${cta} border border-border bg-card/60 backdrop-blur hover:bg-muted`}>
              See how it works
            </a>
          </FadeIn>
          <FadeIn delay={0.32} className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-sm text-muted-foreground">
            {["Local-first models", "Tamper-evident bundles", "EU · NIST · ISO · India views"].map((t) => (
              <span key={t} className="inline-flex items-center gap-2">
                <BadgeCheck className="size-4 text-success" /> {t}
              </span>
            ))}
          </FadeIn>
        </div>
        <FadeIn delay={0.2} y={30}>
          <EvidenceChain />
        </FadeIn>
      </div>
    </section>
  );
}

const MARQUEE = [
  "EU AI Act",
  "NIST AI RMF",
  "ISO/IEC 42001",
  "India DPDP",
  "OWASP LLM Top 10",
  "Ed25519",
  "RFC 8785",
  "DSSE · in-toto",
  "OPA / Rego",
  "LangGraph",
  "Ollama",
];

export function Marquee() {
  const items = [...MARQUEE, ...MARQUEE];
  return (
    <div className="border-y border-border bg-card/40 py-4 [mask-image:linear-gradient(to_right,transparent,#000_12%,#000_88%,transparent)]" aria-hidden>
      <div className="flex w-max animate-marquee gap-12 whitespace-nowrap text-sm font-medium text-muted-foreground">
        {items.map((m, i) => (
          <span key={i} className="inline-flex items-center gap-12">
            {m} <span className="text-brand">◆</span>
          </span>
        ))}
      </div>
    </div>
  );
}

const PILLARS = [
  { icon: ScanSearch, title: "Tools measure, LLMs reason", body: "Every number in a finding comes from a tool's evidence record. A language model chooses tools and interprets results, but never asserts a metric.", span: "lg:col-span-2" },
  { icon: Fingerprint, title: "Everything is evidence", body: "Tool calls, gaps, judgments, waivers and human decisions are all signed, hash-chained ledger records. Nothing is skipped silently." },
  { icon: Gavel, title: "Tiered gates", body: "Rego policies decide quantitative clauses. A cross-family judge panel handles the qualitative ones and abstains when it disagrees. Humans resolve the rest." },
  { icon: Layers, title: "Clause-traceable views", body: "One bundle renders as EU, NIST, ISO and India clause tables. Each row links back to the records that justify it.", span: "lg:col-span-2" },
  { icon: RotateCcw, title: "Replayable", body: "Re-run a sealed audit from its ledger and model cache and get the same bundle identifier, or learn exactly where it diverged." },
  { icon: Wrench, title: "Mitigate, then re-test", body: "An advisor ranks failures, applies mitigations to a sandboxed snapshot, and re-tests on held-out probes to show the real before and after." },
];

export function Pillars() {
  return (
    <section id="pillars" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-24 sm:px-6">
      <Reveal className="mx-auto max-w-2xl text-center">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-brand">Principles</p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">An audit that shows its work</h2>
        <p className="mt-3 text-muted-foreground">Designed so a sceptical reader can check every claim without trusting the auditor.</p>
      </Reveal>
      <Stagger inView className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {PILLARS.map((p) => (
          <StaggerItem key={p.title} className={p.span ?? ""}>
            <div className="hover-lift group h-full rounded-3xl border border-border bg-card p-6">
              <div className="mb-4 grid size-11 place-items-center rounded-2xl bg-accent text-accent-foreground transition group-hover:scale-110">
                <p.icon className="size-5" />
              </div>
              <h3 className="font-semibold">{p.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{p.body}</p>
            </div>
          </StaggerItem>
        ))}
      </Stagger>
    </section>
  );
}

const STEPS = [
  { n: "01", title: "Describe the system", body: "Upload a profile: what it does, its declared risk tier, how to reach it. The orchestrator classifies it and asks you to approve the tier." },
  { n: "02", title: "Agents gather evidence", body: "Risk, fairness, explainability and compliance agents run real tools against the target. Untrusted output is wrapped and screened." },
  { n: "03", title: "Gates decide", body: "Rego thresholds, a judge panel and human review decide every clause. Waivers are time-limited, owned and signed." },
  { n: "04", title: "Seal and advise", body: "The run is sealed as a signed bundle. Open the clause tables, apply mitigations in a sandbox and compare before and after." },
];

export function HowItWorks() {
  return (
    <section id="how" className="relative scroll-mt-20 border-y border-border bg-card/30 py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal className="max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-brand">How it works</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">From profile to sealed bundle</h2>
        </Reveal>
        <div className="relative mt-14 grid gap-6 md:grid-cols-4">
          <div className="absolute left-0 right-0 top-6 hidden h-px bg-gradient-to-r from-transparent via-border to-transparent md:block" aria-hidden />
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 0.08}>
              <div className="relative">
                <span className="relative z-10 grid size-12 place-items-center rounded-2xl bg-primary text-sm font-semibold text-primary-foreground glow">{s.n}</span>
                <h3 className="mt-5 font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

const TERM = [
  { t: "cmd", s: "maat audit --profile examples/profiles/t1_seeded.yaml --planner static" },
  { t: "out", s: "status: pending_review" },
  { t: "out", s: "VG-SEC-01      block      violates asr=1 le 0.05" },
  { t: "out", s: "RG-TRANS-01    block      violates disclosure_rate=0 ge 1" },
  { t: "cmd", s: "maat verify runs/run-20261114-100000-a1b2c3" },
  { t: "ok", s: "OK  bundle sha256:73aa2148…  (31 records)" },
  { t: "cmd", s: "maat render runs/run-20261114-100000-a1b2c3 --regime EU" },
  { t: "out", s: "| AI Act Art. 15(5) | VG-SEC-01 | block | 0 | …" },
];

export function Proof() {
  return (
    <section id="proof" className="mx-auto grid max-w-7xl scroll-mt-20 items-center gap-12 px-4 py-24 sm:px-6 lg:grid-cols-2">
      <Reveal>
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-brand">Proof, not promises</p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Break one byte and verification says so</h2>
        <p className="mt-4 text-muted-foreground">
          <code className="rounded bg-muted px-1.5 py-0.5 text-[13px]">maat verify</code> re-checks the hash chain, every signature, every artifact and the bundle&apos;s Merkle root. Delete or edit a record and it
          reports exactly what changed, with no stack trace.
        </p>
        <ul className="mt-6 space-y-3 text-sm">
          {["Append-only ledger enforced by SQLite triggers", "Records canonicalised with RFC 8785 and signed with Ed25519", "Bundles are DSSE envelopes carrying an in-toto statement"].map((t) => (
            <li key={t} className="flex gap-3">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" /> {t}
            </li>
          ))}
        </ul>
      </Reveal>
      <Reveal delay={0.1}>
        <div className="glass glow overflow-hidden rounded-2xl font-mono text-[13px]">
          <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
            <span className="size-2.5 rounded-full bg-destructive/70" />
            <span className="size-2.5 rounded-full bg-warning/80" />
            <span className="size-2.5 rounded-full bg-success/80" />
            <span className="ml-3 text-xs text-muted-foreground">example session</span>
          </div>
          <div className="space-y-1.5 p-4">
            {TERM.map((l, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.18, duration: 0.35 }}
                className={l.t === "cmd" ? "text-foreground" : l.t === "ok" ? "text-success" : "text-muted-foreground"}
              >
                {l.t === "cmd" && <span className="mr-2 text-brand">$</span>}
                {l.s}
              </motion.div>
            ))}
          </div>
        </div>
      </Reveal>
    </section>
  );
}

const TRUST = [
  { icon: LockKeyhole, title: "Local-first", body: "Models run through Ollama with temperature 0 and a fixed seed. Hosted models are an explicit, off-by-default option. Data egress defaults to local only." },
  { icon: GitCompareArrows, title: "Cross-family judges", body: "No judge shares a model family with the system under audit. A run refuses to start otherwise, unless you pass an explicit ablation flag." },
  { icon: BadgeCheck, title: "Least privilege", body: "Viewers read, reviewers decide and waive, admins apply mitigations. Sensitive artifacts need a reviewer and an explicit click." },
];

export function Trust() {
  return (
    <section id="trust" className="scroll-mt-20 border-t border-border bg-card/30 py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-brand">Trust model</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Built to be audited itself</h2>
        </Reveal>
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {TRUST.map((t, i) => (
            <Reveal key={t.title} delay={i * 0.08}>
              <div className="hover-lift h-full rounded-3xl border border-border bg-card p-6">
                <t.icon className="size-6 text-brand" />
                <h3 className="mt-4 font-semibold">{t.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{t.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function FinalCta() {
  const { token } = useAuth();
  return (
    <section className="relative overflow-hidden py-28">
      <Aurora className="opacity-70" />
      <Reveal className="mx-auto max-w-3xl px-4 text-center">
        <h2 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">Ready to see an audit you can check?</h2>
        <p className="mt-4 text-muted-foreground">Start a run, watch the evidence arrive, then verify the sealed bundle yourself.</p>
        <Link href={token ? "/runs" : "/login"} className={`${cta} glow mt-8 bg-primary text-primary-foreground hover:opacity-90`}>
          {token ? "Open the console" : "Sign in"} <ArrowRight className="size-4" />
        </Link>
      </Reveal>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-border py-10">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 text-sm text-muted-foreground sm:px-6">
        <Wordmark />
        <p>Multi-Agent AI Audit and Trust Framework · Research prototype</p>
      </div>
    </footer>
  );
}

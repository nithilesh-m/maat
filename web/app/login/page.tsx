"use client";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Wordmark } from "@/components/brand/logo";
import { Aurora } from "@/components/landing/aurora";
import { FadeIn } from "@/components/motion";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, token } = useAuth();
  const router = useRouter();
  const [value, setValue] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState<string | null>(null);
  useEffect(() => setReason(sessionStorage.getItem("maat.logout_reason")), []);
  useEffect(() => {
    if (token) router.replace("/runs");
  }, [token, router]);

  return (
    <div className="relative grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden overflow-hidden border-r border-border lg:block">
        <Aurora />
        <div className="relative flex h-full flex-col justify-between p-12">
          <Link href="/" aria-label="MAAT home">
            <Wordmark />
          </Link>
          <FadeIn>
            <h2 className="max-w-md text-balance text-4xl font-semibold leading-tight tracking-tight">
              Every finding traces to a <span className="text-gradient">signed measurement</span>.
            </h2>
            <ul className="mt-8 space-y-3 text-sm text-muted-foreground">
              {["Hash-chained, append-only evidence ledger", "Rules, a judge panel and humans decide each clause", "Re-verify any sealed bundle, anywhere"].map((t) => (
                <li key={t} className="flex items-center gap-3">
                  <ShieldCheck className="size-4 text-success" /> {t}
                </li>
              ))}
            </ul>
          </FadeIn>
          <p className="text-xs text-muted-foreground">Multi-Agent AI Audit and Trust Framework</p>
        </div>
      </div>

      <div className="relative flex flex-col px-6 py-6">
        <div className="flex items-center justify-between lg:justify-end">
          <Link href="/" className="lg:hidden" aria-label="MAAT home">
            <Wordmark />
          </Link>
          <ThemeSwitcher />
        </div>
        <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10">
          <FadeIn>
            <h1 className="text-3xl font-semibold tracking-tight">Sign in to MAAT</h1>
            <p className="mt-2 text-sm text-muted-foreground">Paste the API token your administrator issued. It stays in this tab only.</p>
          </FadeIn>
          {reason === "expired" && (
            <FadeIn>
              <p role="status" className="mt-6 rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
                Your session expired. Please sign in again.
              </p>
            </FadeIn>
          )}
          <FadeIn delay={0.08}>
            <form
              className="mt-8 space-y-4"
              onSubmit={async (e) => {
                e.preventDefault();
                setErr(null);
                setBusy(true);
                try {
                  await login(value.trim());
                } catch (x) {
                  setErr((x as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <div className="space-y-2">
                <label htmlFor="token" className="text-sm font-medium">
                  API token
                </label>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    id="token"
                    type="password"
                    autoComplete="off"
                    spellCheck={false}
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    className="h-11 w-full rounded-xl border border-input bg-background pl-10 pr-3 text-sm outline-none transition focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
                  />
                </div>
              </div>
              {err && (
                <p role="alert" className="text-sm text-destructive">
                  {err}
                </p>
              )}
              <button
                type="submit"
                disabled={!value.trim() || busy}
                className="glow inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-medium text-primary-foreground outline-none transition hover:opacity-90 focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
              >
                {busy && <Loader2 className="size-4 animate-spin" />} Sign in
              </button>
            </form>
          </FadeIn>
        </main>
      </div>
    </div>
  );
}

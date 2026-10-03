"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ClipboardCheck, ListChecks, LogOut, Menu, PlusCircle, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Wordmark } from "@/components/brand/logo";
import { RequireAuth } from "@/components/require-auth";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/runs", label: "Runs", icon: ListChecks, match: (p: string) => p === "/runs" || /^\/runs\/(?!new)/.test(p) },
  { href: "/runs/new", label: "New audit", icon: PlusCircle, match: (p: string) => p === "/runs/new" },
  { href: "/review", label: "Review queue", icon: ClipboardCheck, match: (p: string) => p.startsWith("/review") },
  { href: "/verify", label: "Verify", icon: ShieldCheck, match: (p: string) => p.startsWith("/verify") },
];

const ROLE_DOT = { viewer: "bg-muted-foreground", reviewer: "bg-info", admin: "bg-success" } as const;

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {NAV.map((n) => {
        const active = n.match(path);
        return (
          <Link
            key={n.href}
            href={n.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 ${
              active ? "text-foreground" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {active && (
              <motion.span
                layoutId="nav-active"
                className="absolute inset-0 rounded-xl bg-accent ring-1 ring-border"
                transition={{ type: "spring", stiffness: 420, damping: 36 }}
              />
            )}
            <n.icon className="relative size-4" aria-hidden />
            <span className="relative">{n.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function UserBox() {
  const { role, logout } = useAuth();
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 rounded-xl border border-border bg-card/60 px-3 py-2 text-xs">
        <span className={`size-2 rounded-full ${ROLE_DOT[role ?? "viewer"]}`} aria-hidden />
        <span className="text-muted-foreground">Signed in as</span>
        <span className="font-medium">{role}</span>
      </div>
      <button
        type="button"
        onClick={() => logout()}
        className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground outline-none transition hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <LogOut className="size-4" aria-hidden /> Logout
      </button>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <RequireAuth>
      <div className="relative min-h-screen lg:grid lg:grid-cols-[17rem_1fr]">
        <aside className="sticky top-0 hidden h-screen flex-col justify-between border-r border-sidebar-border bg-sidebar px-4 py-5 lg:flex">
          <div className="space-y-8">
            <Link href="/" aria-label="MAAT home" className="block px-2">
              <Wordmark />
            </Link>
            <NavLinks />
          </div>
          <UserBox />
        </aside>

        <div className="min-w-0">
          <header className="glass sticky top-0 z-30 flex items-center gap-3 border-x-0 border-t-0 px-4 py-3 sm:px-6">
            <button
              type="button"
              aria-label="Open menu"
              className="grid size-9 place-items-center rounded-lg border border-border lg:hidden"
              onClick={() => setOpen(true)}
            >
              <Menu className="size-4" />
            </button>
            <Link href="/" className="lg:hidden" aria-label="MAAT home">
              <Wordmark />
            </Link>
            <div className="ml-auto flex items-center gap-2">
              <ThemeSwitcher />
            </div>
          </header>
          <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6">{children}</main>
        </div>

        <AnimatePresence>
          {open && (
            <motion.div className="fixed inset-0 z-50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <button aria-label="Close menu" className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
              <motion.div
                initial={{ x: "-100%" }}
                animate={{ x: 0 }}
                exit={{ x: "-100%" }}
                transition={{ type: "spring", stiffness: 380, damping: 38 }}
                className="absolute inset-y-0 left-0 flex w-72 flex-col justify-between border-r border-sidebar-border bg-sidebar px-4 py-5"
              >
                <div className="space-y-8">
                  <div className="flex items-center justify-between px-2">
                    <Wordmark />
                    <button aria-label="Close menu" onClick={() => setOpen(false)}>
                      <X className="size-4" />
                    </button>
                  </div>
                  <NavLinks onNavigate={() => setOpen(false)} />
                </div>
                <UserBox />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </RequireAuth>
  );
}

"use client";
import { Monitor, Moon, Palette, Sun } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";
import { ACCENTS, useAccent } from "@/components/accent";

const MODES = [
  ["light", Sun, "Light"],
  ["dark", Moon, "Dark"],
  ["system", Monitor, "System"],
] as const;

export function ThemeSwitcher({ compact = false }: { compact?: boolean }) {
  const { theme, setTheme } = useTheme();
  const { accent, setAccent } = useAccent();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const Icon = !mounted ? Sun : theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;
  return (
    <div className="relative" ref={box}>
      <button
        type="button"
        aria-label="Theme and colour"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
        className="grid size-9 place-items-center rounded-lg border border-border bg-background/60 text-foreground transition hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
      >
        <Icon className="size-4" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="dialog"
            aria-label="Theme settings"
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.16 }}
            className={`glass absolute z-50 mt-2 w-60 rounded-xl p-3 shadow-xl ${compact ? "left-0" : "right-0"}`}
          >
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Mode</p>
            <div className="grid grid-cols-3 gap-1 rounded-lg bg-muted p-1">
              {MODES.map(([v, I, label]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setTheme(v)}
                  aria-pressed={mounted && theme === v}
                  className={`flex flex-col items-center gap-1 rounded-md py-1.5 text-xs transition ${
                    mounted && theme === v ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <I className="size-4" />
                  {label}
                </button>
              ))}
            </div>
            <p className="mb-2 mt-3 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              <Palette className="size-3" /> Accent
            </p>
            <div className="flex gap-2">
              {ACCENTS.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  aria-label={`${a.label} accent`}
                  aria-pressed={accent === a.id}
                  onClick={() => setAccent(a.id)}
                  className={`size-7 rounded-full ring-offset-2 ring-offset-background transition hover:scale-110 ${
                    accent === a.id ? "ring-2 ring-foreground" : ""
                  }`}
                  style={{ background: `oklch(0.62 0.2 ${a.hue})` }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

export const ACCENTS = [
  { id: "violet", label: "Violet", hue: 285 },
  { id: "ocean", label: "Ocean", hue: 235 },
  { id: "emerald", label: "Emerald", hue: 160 },
  { id: "ember", label: "Ember", hue: 45 },
  { id: "rose", label: "Rose", hue: 5 },
] as const;
export type AccentId = (typeof ACCENTS)[number]["id"];
const KEY = "maat.accent";

/** Applied before paint (see app/layout.tsx) so there is no flash of the wrong accent. */
export const ACCENT_BOOT_SCRIPT = `try{var a=localStorage.getItem("${KEY}");if(a)document.documentElement.dataset.accent=a}catch(e){}`;

const Ctx = createContext<{ accent: AccentId; setAccent: (a: AccentId) => void }>({
  accent: "violet",
  setAccent: () => {},
});

export function AccentProvider({ children }: { children: React.ReactNode }) {
  const [accent, setState] = useState<AccentId>("violet");
  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY) as AccentId | null;
      if (saved && ACCENTS.some((a) => a.id === saved)) setState(saved);
    } catch {
      /* storage unavailable: keep the default */
    }
  }, []);
  const setAccent = useCallback((a: AccentId) => {
    setState(a);
    document.documentElement.dataset.accent = a;
    try {
      localStorage.setItem(KEY, a);
    } catch {
      /* ignore */
    }
  }, []);
  return <Ctx.Provider value={{ accent, setAccent }}>{children}</Ctx.Provider>;
}

export const useAccent = () => useContext(Ctx);

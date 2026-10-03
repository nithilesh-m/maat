"use client";
import { ScoreRing, Stagger, StaggerItem } from "@/components/motion";
import type { Scores } from "@/lib/types";

export function ScoreCards({ scores }: { scores: Scores }) {
  const entries = Object.entries(scores.regimes);
  return (
    <Stagger className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {entries.map(([reg, s]) => (
        <StaggerItem key={reg}>
          <div className="hover-lift rounded-3xl border border-border bg-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold tracking-tight">{reg}</h3>
              <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] text-accent-foreground">regime view</span>
            </div>
            <dl className="grid grid-cols-3 gap-2">
              <div><dt className="sr-only">Coverage</dt><dd><ScoreRing value={s.cc} label="Coverage" size={68} stroke={7} /></dd></div>
              <div><dt className="sr-only">Adequacy</dt><dd><ScoreRing value={s.as} label="Adequacy" size={68} stroke={7} /></dd></div>
              <div><dt className="sr-only">Measured</dt><dd><ScoreRing value={s.mer} label="Measured" size={68} stroke={7} /></dd></div>
            </dl>
          </div>
        </StaggerItem>
      ))}
    </Stagger>
  );
}

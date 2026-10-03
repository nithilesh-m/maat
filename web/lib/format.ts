import type { GateOutcome } from "./types";

export const fmtScore = (x: number | null | undefined) => (x == null ? "–" : x.toFixed(3));
export const fmtPct = (x: number | null | undefined) =>
  x == null ? "–" : `${(x * 100).toFixed(1)}%`;
export const shortHash = (h: string) => h.slice(0, 15);

export function outcomeTone(o: GateOutcome): "success" | "danger" | "warning" | "muted" {
  if (o === "pass") return "success";
  if (o === "block" || o === "fail") return "danger";
  if (o === "waive" || o === "abstain") return "warning";
  return "muted";
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

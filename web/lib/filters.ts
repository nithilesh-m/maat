import type { ClauseRow, GateOutcome } from "./types";

export function filterRows(
  rows: ClauseRow[],
  f: { outcome?: GateOutcome | ""; gate?: string; control?: string; minA?: number },
) {
  return rows.filter(
    (r) =>
      (!f.outcome || r.outcome === f.outcome) &&
      (!f.gate || r.control_id.startsWith(`${f.gate}-`)) &&
      (!f.control || r.control_id.toLowerCase().includes(f.control.toLowerCase())) &&
      (f.minA == null || r.adequacy >= f.minA),
  );
}

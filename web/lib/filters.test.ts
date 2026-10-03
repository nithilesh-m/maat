import { describe, expect, it } from "vitest";
import { filterRows } from "./filters";
import type { ClauseRow } from "./types";

const R = (control_id: string, outcome: ClauseRow["outcome"], adequacy: number): ClauseRow => ({
  regime: "EU",
  regime_clause: `c-${control_id}`,
  control_id,
  outcome,
  adequacy,
  evidence: [],
  waiver_id: null,
});

describe("filterRows", () => {
  const rows = [R("VG-SEC-01", "block", 0), R("RG-TRANS-01", "pass", 3), R("VG-FAIR-01", "waive", 1)];
  it("by outcome", () =>
    expect(filterRows(rows, { outcome: "block" }).map((r) => r.control_id)).toEqual(["VG-SEC-01"]));
  it("by gate prefix", () => expect(filterRows(rows, { gate: "VG" })).toHaveLength(2));
  it("by control substring", () => expect(filterRows(rows, { control: "trans" })).toHaveLength(1));
  it("by min adequacy", () => expect(filterRows(rows, { minA: 1 })).toHaveLength(2));
  it("no filters returns everything, empty outcome means any", () => {
    expect(filterRows(rows, {})).toHaveLength(3);
    expect(filterRows(rows, { outcome: "" })).toHaveLength(3);
  });
});

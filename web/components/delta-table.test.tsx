import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DeltaTable } from "./delta-table";

describe("DeltaTable", () => {
  it("marks improvements and regressions", () => {
    render(
      <DeltaTable
        rows={[
          { control_id: "VG-SEC-01", regime_clause: "AI Act Art. 15(5)", before_outcome: "block", after_outcome: "pass", before_a: 0, after_a: 3 },
          { control_id: "VG-ACC-01", regime_clause: "AI Act Art. 15(1)", before_outcome: "pass", after_outcome: "block", before_a: 2, after_a: 0 },
        ]}
      />,
    );
    expect(screen.getByLabelText("improved")).toBeTruthy();
    expect(screen.getByLabelText("regressed")).toBeTruthy();
  });
  it("shows an empty state for no rows", () => {
    render(<DeltaTable rows={[]} />);
    expect(screen.getByText(/No clauses changed/)).toBeTruthy();
  });
});

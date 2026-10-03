import { describe, expect, it } from "vitest";
import { validateWaiver } from "./waiver";

const NOW = new Date("2027-04-01T00:00:00Z");
const base = {
  id: "W-1",
  clause_id: "VG-SEC-01",
  owner: "PO",
  scope: "dev",
  expiry: "2027-04-10T00:00:00Z",
  compensations: ["assistive mode"],
};

describe("validateWaiver", () => {
  it("valid", () => expect(validateWaiver(base, NOW)).toEqual([]));
  it("past expiry", () =>
    expect(validateWaiver({ ...base, expiry: "2027-03-01T00:00:00Z" }, NOW)).toContain("Expiry must be in the future"));
  it("too long", () =>
    expect(validateWaiver({ ...base, expiry: "2027-12-01T00:00:00Z" }, NOW)).toContain("Expiry must be within 90 days"));
  it("needs compensation", () =>
    expect(validateWaiver({ ...base, compensations: [" "] }, NOW)).toContain("At least one compensating measure is required"));
  it("requires text fields and a valid date", () => {
    const errs = validateWaiver({ ...base, owner: "", expiry: "nope" }, NOW);
    expect(errs).toContain("owner is required");
    expect(errs).toContain("Expiry is not a valid date");
  });
});

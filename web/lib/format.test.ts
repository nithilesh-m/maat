import { describe, expect, it } from "vitest";
import { fmtPct, fmtScore, outcomeTone, shortHash } from "./format";

describe("format", () => {
  it("scores", () => {
    expect(fmtScore(0.91234)).toBe("0.912");
    expect(fmtScore(null)).toBe("–");
  });
  it("pct", () => expect(fmtPct(0.9123)).toBe("91.2%"));
  it("hash", () => expect(shortHash("sha256:abcdef0123456789")).toBe("sha256:abcdef01"));
  it("tones", () => {
    expect(outcomeTone("pass")).toBe("success");
    expect(outcomeTone("block")).toBe("danger");
    expect(outcomeTone("waive")).toBe("warning");
    expect(outcomeTone("not_applicable")).toBe("muted");
  });
});

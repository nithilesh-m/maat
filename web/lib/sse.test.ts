import { describe, expect, it } from "vitest";
import { EventBuffer, backoffMs } from "./sse";

describe("EventBuffer (Review Focus #2)", () => {
  it("dedups and orders by seq; tracks lastSeq", () => {
    const b = new EventBuffer();
    expect(b.add({ seq: 1, kind: "tool_started", payload: {} })).toBe(true);
    expect(b.add({ seq: 0, kind: "plan_created", payload: {} })).toBe(true);
    expect(b.add({ seq: 1, kind: "tool_started", payload: {} })).toBe(false);
    expect(b.events.map((e) => e.seq)).toEqual([0, 1]);
    expect(b.lastSeq).toBe(1);
  });
  it("empty buffer has lastSeq -1", () => expect(new EventBuffer().lastSeq).toBe(-1));
  it("terminal detection", () => {
    const b = new EventBuffer();
    b.add({ seq: 0, kind: "run_sealed", payload: {} });
    expect(b.isTerminal()).toBe(true);
    const f = new EventBuffer();
    f.add({ seq: 0, kind: "run_failed", payload: {} });
    expect(f.isTerminal()).toBe(true);
    const o = new EventBuffer();
    o.add({ seq: 0, kind: "gate_decision", payload: {} });
    expect(o.isTerminal()).toBe(false);
  });
  it("backoff caps at 15s", () => {
    expect([0, 1, 2, 3, 4, 10].map(backoffMs)).toEqual([1000, 2000, 4000, 8000, 15000, 15000]);
  });
});

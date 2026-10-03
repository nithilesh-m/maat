import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/hooks", () => ({ useRun: vi.fn() }));
vi.mock("@/components/approval-panel", () => ({ ApprovalPanel: () => <div>approval-form</div> }));
import { useRun } from "@/lib/hooks";
import { SealedGuard } from "./sealed-guard";

const set = (data: unknown, extra: object = {}) =>
  (useRun as unknown as ReturnType<typeof vi.fn>).mockReturnValue({ data, isLoading: false, ...extra });

describe("SealedGuard (Review Focus #3)", () => {
  it("in progress", () => {
    set({ status: "running" });
    render(<SealedGuard runId="r">x</SealedGuard>);
    expect(screen.getByText(/Audit in progress/)).toBeTruthy();
  });
  it("queued is also in progress", () => {
    set({ status: "queued" });
    render(<SealedGuard runId="r">x</SealedGuard>);
    expect(screen.getByText(/Audit in progress/)).toBeTruthy();
  });
  it("paused shows approval, not an error", () => {
    set({ status: "paused", pending_approval: { a: 1 } });
    render(<SealedGuard runId="r">x</SealedGuard>);
    expect(screen.getByText("approval-form")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
  it("paused without a stored question says awaiting approval", () => {
    set({ status: "paused", pending_approval: null });
    render(<SealedGuard runId="r">x</SealedGuard>);
    expect(screen.getByText(/Awaiting approval/)).toBeTruthy();
  });
  it("complete renders children", () => {
    set({ status: "complete" });
    render(
      <SealedGuard runId="r">
        <p>content</p>
      </SealedGuard>,
    );
    expect(screen.getByText("content")).toBeTruthy();
  });
  it("failed shows the error", () => {
    set({ status: "failed", error: "boom" });
    render(<SealedGuard runId="r">x</SealedGuard>);
    expect(screen.getByRole("alert").textContent).toContain("boom");
  });
});

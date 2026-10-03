import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { AuthProvider, useAuth } from "./auth";

function Probe() {
  const a = useAuth();
  return (
    <div>
      <span data-testid="t">{a.token ?? "none"}</span>
      <button onClick={() => a.logout("expired")}>out</button>
    </div>
  );
}

describe("auth (Review Focus #1)", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("restores token from sessionStorage and logout clears it", async () => {
    sessionStorage.setItem("maat.token", "abc");
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    expect(screen.getByTestId("t").textContent).toBe("abc");
    await act(async () => screen.getByText("out").click());
    expect(sessionStorage.getItem("maat.token")).toBeNull();
    expect(sessionStorage.getItem("maat.logout_reason")).toBe("expired");
  });

  it("login rejects an invalid token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "invalid token" }), { status: 401 })),
    );
    let api: ReturnType<typeof useAuth> | null = null;
    function Grab() {
      api = useAuth();
      return null;
    }
    render(
      <AuthProvider>
        <Grab />
      </AuthProvider>,
    );
    await expect(api!.login("bad")).rejects.toThrow("Invalid token");
    expect(sessionStorage.getItem("maat.token")).toBeNull();
  });

  it("derives roles from probe statuses: viewer 403, reviewer 422+403, admin 422+422", async () => {
    const answer = (runs: number, apply: number) =>
      vi.fn(async (req: Request) => {
        const url = new URL(req.url);
        if (url.pathname.endsWith("/mitigations/apply"))
          return new Response("{}", { status: apply });
        if (req.method === "POST") return new Response("{}", { status: runs });
        return new Response("[]", { status: 200 });
      });
    for (const [runs, apply, role] of [
      [403, 403, "viewer"],
      [422, 403, "reviewer"],
      [422, 422, "admin"],
    ] as const) {
      sessionStorage.clear();
      vi.stubGlobal("fetch", answer(runs, apply));
      let api: ReturnType<typeof useAuth> | null = null;
      function Grab() {
        api = useAuth();
        return <span data-testid="r">{api.role ?? "none"}</span>;
      }
      const { unmount } = render(
        <AuthProvider>
          <Grab />
        </AuthProvider>,
      );
      await act(async () => {
        await api!.login("tok");
      });
      expect(screen.getByTestId("r").textContent).toBe(role);
      unmount();
    }
  });
});

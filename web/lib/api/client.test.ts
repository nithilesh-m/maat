import { describe, expect, it } from "vitest";
import { ApiError, apiBase, unwrap } from "./client";

describe("api client", () => {
  it("defaults the base URL", () => {
    expect(apiBase()).toBe("http://127.0.0.1:8080");
  });
  it("unwrap returns data on success", () => {
    expect(
      unwrap({ data: { ok: true }, error: undefined, response: new Response(null, { status: 200 }) }),
    ).toEqual({ ok: true });
  });
  it("unwrap throws ApiError with detail", () => {
    const res = {
      data: undefined,
      error: { detail: "run not sealed yet" },
      response: new Response(null, { status: 409 }),
    };
    expect(() => unwrap(res)).toThrowError(ApiError);
    try {
      unwrap(res);
    } catch (e) {
      expect((e as ApiError).status).toBe(409);
      expect((e as ApiError).detail).toBe("run not sealed yet");
    }
  });
});

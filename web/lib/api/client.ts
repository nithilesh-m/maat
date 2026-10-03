import createClient from "openapi-fetch";
import type { paths } from "./schema";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`${status}: ${detail}`);
  }
}

export function apiBase(): string {
  return process.env.NEXT_PUBLIC_MAAT_API ?? "http://127.0.0.1:8080";
}

export function createApi(token: string | null) {
  return createClient<paths>({
    baseUrl: apiBase(),
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

type Res<T> = { data?: T; error?: unknown; response: Response };

export function unwrap<T>(res: Res<T>): T {
  if (res.response.ok && res.data !== undefined) return res.data;
  const err = res.error as { detail?: unknown } | undefined;
  const detail =
    typeof err?.detail === "string" ? err.detail : res.response.statusText || "request failed";
  throw new ApiError(res.response.status, detail);
}

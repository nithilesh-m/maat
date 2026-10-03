"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { createApi } from "./api/client";
import type { Role } from "./types";

type Auth = {
  token: string | null;
  role: Role | null;
  ready: boolean;
  login: (t: string) => Promise<void>;
  logout: (reason?: string) => void;
};
const Ctx = createContext<Auth | null>(null);
const KEY = "maat.token";
const ROLE_KEY = "maat.role";

/**
 * API v1 has no "whoami" endpoint (recorded in docs/api/v2-requests.md), so the role is probed
 * with two requests that fail validation before doing anything:
 *   POST /runs {}                           403 viewer | 422 reviewer or admin
 *   POST /runs/_probe/mitigations/apply {}  403 reviewer | 422 admin
 */
async function probeRole(token: string): Promise<Role> {
  const api = createApi(token);
  const create = await api.POST("/api/v1/runs", { body: {} as never });
  if (create.response.status === 403) return "viewer";
  const apply = await api.POST("/api/v1/runs/{run_id}/mitigations/apply", {
    params: { path: { run_id: "_probe" } },
    body: {} as never,
  });
  return apply.response.status === 403 ? "reviewer" : "admin";
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const t = sessionStorage.getItem(KEY);
    if (t) {
      setToken(t);
      setRole((sessionStorage.getItem(ROLE_KEY) as Role) ?? "viewer");
    }
    setReady(true);
  }, []);

  const login = useCallback(async (t: string) => {
    const r = await createApi(t).GET("/api/v1/runs", {
      params: { query: { limit: 1 } },
    });
    if (r.response.status === 401) throw new Error("Invalid token");
    if (!r.response.ok) throw new Error(`Server error ${r.response.status}`);
    const found = await probeRole(t);
    sessionStorage.setItem(KEY, t);
    sessionStorage.setItem(ROLE_KEY, found);
    sessionStorage.removeItem("maat.logout_reason");
    setToken(t);
    setRole(found);
  }, []);

  const logout = useCallback((reason?: string) => {
    sessionStorage.removeItem(KEY);
    sessionStorage.removeItem(ROLE_KEY);
    if (reason) sessionStorage.setItem("maat.logout_reason", reason);
    setToken(null);
    setRole(null);
  }, []);

  return <Ctx.Provider value={{ token, role, ready, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): Auth {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}

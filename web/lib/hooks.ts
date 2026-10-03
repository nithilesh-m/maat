"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { createApi, unwrap } from "./api/client";
import { useAuth } from "./auth";
import type {
  DeltaRow,
  EvidenceRecord,
  Finding,
  GateDecision,
  JudgeVote,
  MitigationPlan,
  RegimeView,
  RunRow,
  Scores,
  VerifyReport,
} from "./types";

function useApi() {
  const { token } = useAuth();
  return useMemo(() => createApi(token), [token]);
}
const LIVE = new Set(["queued", "running", "paused"]);
const cast = <T,>(x: unknown) => x as T;

export interface QueueItem {
  run_id: string;
  clause_id: string;
  judges: JudgeVote[];
  rationale: string;
}
export interface WaiverRow {
  run_id: string;
  record_id: string;
  waiver: {
    id: string;
    clause_id: string;
    owner: string;
    scope: string;
    expiry: string;
    compensations: string[];
  };
}
export interface Mitigations {
  plans: MitigationPlan[];
  manual: string[];
}
export interface DeltaResponse {
  rows: DeltaRow[];
  summary: Record<string, number | Record<string, number> | null>;
}
export interface RecordFilters {
  type?: string;
  agent?: string;
  limit?: number;
  offset?: number;
}

/* ---------------------------------- queries --------------------------------- */

export function useRuns() {
  const api = useApi();
  return useQuery({
    queryKey: ["runs"],
    queryFn: async () => cast<RunRow[]>(unwrap(await api.GET("/api/v1/runs", {}))),
    refetchInterval: 5000,
  });
}

export function useRun(runId: string) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "run"],
    queryFn: async () =>
      cast<RunRow>(
        unwrap(await api.GET("/api/v1/runs/{run_id}", { params: { path: { run_id: runId } } })),
      ),
    refetchInterval: (q) => (q.state.data && LIVE.has(q.state.data.status) ? 2000 : false),
  });
}

export function useDecisions(runId: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "decisions"],
    enabled,
    queryFn: async () =>
      cast<GateDecision[]>(
        unwrap(
          await api.GET("/api/v1/runs/{run_id}/decisions", { params: { path: { run_id: runId } } }),
        ),
      ),
  });
}

export function useFindings(runId: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "findings"],
    enabled,
    queryFn: async () =>
      cast<Finding[]>(
        unwrap(
          await api.GET("/api/v1/runs/{run_id}/findings", { params: { path: { run_id: runId } } }),
        ),
      ),
  });
}

export function useView(runId: string, regime: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "view", regime],
    enabled,
    queryFn: async () =>
      cast<RegimeView>(
        unwrap(
          await api.GET("/api/v1/runs/{run_id}/views/{regime}", {
            params: { path: { run_id: runId, regime } },
          }),
        ),
      ),
  });
}

export function useScores(runId: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "scores"],
    enabled,
    queryFn: async () =>
      cast<Scores>(
        unwrap(
          await api.GET("/api/v1/runs/{run_id}/scores", { params: { path: { run_id: runId } } }),
        ),
      ),
  });
}

export function useRecords(runId: string, filters: RecordFilters = {}, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "records", filters],
    enabled,
    queryFn: async () =>
      cast<EvidenceRecord[]>(
        unwrap(
          await api.GET("/api/v1/runs/{run_id}/records", {
            params: { path: { run_id: runId }, query: { limit: 1000, ...filters } },
          }),
        ),
      ),
  });
}

export function useRecord(runId: string, recordId: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "record", recordId],
    enabled,
    queryFn: async () =>
      cast<EvidenceRecord>(
        unwrap(
          await api.GET("/api/v1/records/{run_id}/{record_id}", {
            params: { path: { run_id: runId, record_id: recordId } },
          }),
        ),
      ),
  });
}

export function useVerify(runId: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "verify"],
    enabled,
    queryFn: async () =>
      cast<VerifyReport>(
        unwrap(
          await api.GET("/api/v1/runs/{run_id}/verify", { params: { path: { run_id: runId } } }),
        ),
      ),
  });
}

export function useReviewQueue() {
  const api = useApi();
  return useQuery({
    queryKey: ["review-queue"],
    queryFn: async () => cast<QueueItem[]>(unwrap(await api.GET("/api/v1/review-queue", {}))),
  });
}

export function useWaivers() {
  const api = useApi();
  return useQuery({
    queryKey: ["waivers"],
    queryFn: async () => cast<WaiverRow[]>(unwrap(await api.GET("/api/v1/waivers", {}))),
  });
}

export function useMitigations(runId: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "mitigations"],
    enabled,
    queryFn: async () =>
      cast<Mitigations>(
        unwrap(
          await api.GET("/api/v1/runs/{run_id}/mitigations", {
            params: { path: { run_id: runId } },
          }),
        ),
      ),
  });
}

export function useChildren(runId: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "children"],
    enabled,
    queryFn: async () =>
      cast<string[]>(
        unwrap(
          await api.GET("/api/v1/runs/{run_id}/children", { params: { path: { run_id: runId } } }),
        ),
      ),
    refetchInterval: 4000,
  });
}

export function useDelta(runId: string, childId: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [runId, "delta", childId],
    enabled,
    queryFn: async () =>
      cast<DeltaResponse>(
        unwrap(
          await api.GET("/api/v1/runs/{run_id}/delta/{child_id}", {
            params: { path: { run_id: runId, child_id: childId } },
          }),
        ),
      ),
  });
}

/* --------------------------------- mutations -------------------------------- */

export function useCreateRun() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      profile_yaml: string;
      planner: "agents" | "static";
      auto_approve: boolean;
    }) =>
      cast<{ run_id: string; status: string }>(
        unwrap(await api.POST("/api/v1/runs", { body: body as never })),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export function useApprove(runId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { approve_tier: boolean; ers: Record<string, unknown> | null }) =>
      unwrap(
        await api.POST("/api/v1/runs/{run_id}/approval", {
          params: { path: { run_id: runId } },
          body: body as never,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: [runId] }),
  });
}

export function useReview(runId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { clause_id: string; label: string; rationale: string }) =>
      unwrap(
        await api.POST("/api/v1/runs/{run_id}/reviews", {
          params: { path: { run_id: runId } },
          body: body as never,
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [runId] });
      qc.invalidateQueries({ queryKey: ["review-queue"] });
    },
  });
}

export function useWaiver(runId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      id: string;
      clause_id: string;
      owner: string;
      scope: string;
      expiry: string;
      compensations: string[];
    }) =>
      unwrap(
        await api.POST("/api/v1/runs/{run_id}/waivers", {
          params: { path: { run_id: runId } },
          body: body as never,
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [runId] });
      qc.invalidateQueries({ queryKey: ["waivers"] });
    },
  });
}

export function useApplyMitigations(runId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (mitigation_ids: string[]) =>
      unwrap(
        await api.POST("/api/v1/runs/{run_id}/mitigations/apply", {
          params: { path: { run_id: runId } },
          body: { mitigation_ids } as never,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: [runId, "children"] }),
  });
}

export function useVerifyUpload() {
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (file: File): Promise<VerifyReport> => {
      const { apiBase, ApiError } = await import("./api/client");
      const form = new FormData();
      form.append("file", file);
      const r = await fetch(`${apiBase()}/api/v1/verify`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new ApiError(r.status, body.detail ?? r.statusText);
      return body as VerifyReport;
    },
  });
}

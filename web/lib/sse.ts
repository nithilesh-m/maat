import { fetchEventSource } from "@microsoft/fetch-event-source";
import { apiBase } from "./api/client";
import type { MaatEvent } from "./types";

export class EventBuffer {
  private bySeq = new Map<number, MaatEvent>();
  add(e: MaatEvent): boolean {
    if (this.bySeq.has(e.seq)) return false;
    this.bySeq.set(e.seq, e);
    return true;
  }
  get events(): MaatEvent[] {
    return [...this.bySeq.values()].sort((a, b) => a.seq - b.seq);
  }
  get lastSeq(): number {
    return this.bySeq.size ? Math.max(...this.bySeq.keys()) : -1;
  }
  isTerminal(): boolean {
    return this.events.some((e) => e.kind === "run_sealed" || e.kind === "run_failed");
  }
}

export const backoffMs = (attempt: number) => Math.min(1000 * 2 ** attempt, 15000);

export type StreamState = "open" | "retrying" | "done" | "unauthorized";

class Unauthorized extends Error {}
class Done extends Error {}

/**
 * Streams run events with the bearer token. `Last-Event-ID` is sent from the buffer on every
 * (re)subscription, and the buffer drops duplicates, so a reconnect never repeats or loses events.
 * The caller re-subscribes after `retrying` so the header is fresh (see the live page).
 */
export function subscribeRunEvents(
  runId: string,
  token: string,
  buffer: EventBuffer,
  onChange: () => void,
  onState: (s: StreamState) => void,
): () => void {
  const ctrl = new AbortController();
  void fetchEventSource(`${apiBase()}/api/v1/runs/${runId}/events`, {
    signal: ctrl.signal,
    openWhenHidden: true,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(buffer.lastSeq >= 0 ? { "Last-Event-ID": String(buffer.lastSeq) } : {}),
    },
    async onopen(res) {
      if (res.status === 401) throw new Unauthorized();
      if (!res.ok) throw new Error(`events ${res.status}`);
      onState("open");
    },
    onmessage(ev) {
      if (!ev.event) return;
      const added = buffer.add({
        seq: Number(ev.id),
        kind: ev.event,
        payload: ev.data ? JSON.parse(ev.data) : {},
      });
      if (added) onChange();
      if (buffer.isTerminal()) throw new Done();
    },
    onclose() {
      throw new Error("stream closed");
    },
    onerror(err) {
      if (err instanceof Unauthorized) {
        onState("unauthorized");
        throw err;
      }
      if (err instanceof Done || buffer.isTerminal()) {
        onState("done");
        throw err;
      }
      onState("retrying");
      throw err; // stop this attempt; the page schedules a fresh subscription with backoff
    },
  }).catch(() => undefined);
  return () => ctrl.abort();
}

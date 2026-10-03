"use client";
import { ArrowRight, Radio } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApprovalPanel } from "@/components/approval-panel";
import { EventFeed } from "@/components/event-feed";
import { PageHeader } from "@/components/page-header";
import { StatusPill } from "@/components/status-pill";
import { useAuth } from "@/lib/auth";
import { useRun } from "@/lib/hooks";
import { EventBuffer, backoffMs, subscribeRunEvents } from "@/lib/sse";
import type { MaatEvent } from "@/lib/types";

export default function LivePage() {
  const { id } = useParams<{ id: string }>();
  const { token, logout } = useAuth();
  const run = useRun(id);
  const [buf] = useState(() => new EventBuffer());
  const [events, setEvents] = useState<MaatEvent[]>([]);
  const [state, setState] = useState("connecting");
  const status = run.data?.status;
  const statusRef = useRef(status);
  useEffect(() => {
    statusRef.current = status;
  }, [status]);
  const streaming = status === "queued" || status === "running";
  const subscribe = streaming || status === "complete"; // complete runs replay their history once

  useEffect(() => {
    // Re-subscribe whenever the status flips back to a live one (for example after an approval).
    if (!token || !subscribe) return;
    let cancel = () => {};
    let attempt = 0;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const start = () => {
      cancel = subscribeRunEvents(id, token, buf, () => setEvents(buf.events), (s) => {
        setState(s);
        if (s === "unauthorized") logout("expired");
        if (s === "open") attempt = 0;
        const live = statusRef.current === "queued" || statusRef.current === "running";
        if (s === "retrying" && !stopped && live) {
          cancel();
          timer = setTimeout(start, backoffMs(attempt++));
        }
      });
    };
    start();
    return () => {
      stopped = true;
      clearTimeout(timer);
      cancel();
    };
  }, [id, token, logout, subscribe, buf]);

  return (
    <>
      <PageHeader
        eyebrow="Live"
        title={<span className="font-mono text-2xl">{id}</span>}
        actions={
          <>
            {status && <StatusPill status={status} />}
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Radio className={`size-3.5 ${state === "open" ? "text-success" : ""}`} /> stream: {state}
            </span>
          </>
        }
      />
      <div className="space-y-5">
        {status === "paused" && run.data?.pending_approval && <ApprovalPanel runId={id} question={run.data.pending_approval} />}
        {status === "failed" && <p role="alert" className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-destructive">Run failed: {run.data?.error}</p>}
        {status === "complete" && (
          <Link className="inline-flex items-center gap-2 rounded-xl bg-success/12 px-4 py-2.5 text-sm font-medium text-success ring-1 ring-success/30" href={`/runs/${id}`}>
            Open results <ArrowRight className="size-4" />
          </Link>
        )}
        <EventFeed events={events} />
        {!streaming && events.length === 0 && status !== "paused" && (
          <p className="text-sm text-muted-foreground">This run is not streaming. Open the results to inspect it.</p>
        )}
      </div>
    </>
  );
}

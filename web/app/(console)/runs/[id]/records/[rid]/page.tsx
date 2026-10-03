"use client";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { EvidenceRecordCard } from "@/components/evidence-record";
import { ErrorNote, SkeletonRows } from "@/components/page-header";
import { RunFrame } from "@/components/run-frame";
import { useRecord, useRecords } from "@/lib/hooks";

export default function RecordPage() {
  const { id, rid } = useParams<{ id: string; rid: string }>();
  return (
    <RunFrame id={id} active="Overview">
      <Body id={id} rid={rid} />
    </RunFrame>
  );
}

function Body({ id, rid }: { id: string; rid: string }) {
  const rec = useRecord(id, rid);
  const all = useRecords(id, {});
  if (rec.isLoading) return <SkeletonRows rows={3} />;
  if (rec.error || !rec.data) return <ErrorNote error={rec.error ?? new Error("record not found")} />;
  const sorted = [...(all.data ?? [])].sort((a, b) => a.seq - b.seq);
  const i = sorted.findIndex((r) => r.id === rid);
  const prev = i > 0 ? sorted[i - 1] : null;
  const next = i >= 0 && i < sorted.length - 1 ? sorted[i + 1] : null;
  return (
    <div className="space-y-4">
      <EvidenceRecordCard runId={id} record={rec.data} />
      <nav className="flex justify-between text-sm" aria-label="Record navigation">
        {prev ? <Link className="inline-flex items-center gap-1 underline-offset-4 hover:underline" href={`/runs/${id}/records/${prev.id}`}><ChevronLeft className="size-4" />seq {prev.seq}</Link> : <span />}
        {next ? <Link className="inline-flex items-center gap-1 underline-offset-4 hover:underline" href={`/runs/${id}/records/${next.id}`}>seq {next.seq}<ChevronRight className="size-4" /></Link> : <span />}
      </nav>
    </div>
  );
}

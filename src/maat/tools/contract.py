from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from maat.evidence.artifacts import ArtifactStore
from maat.evidence.ledger import Ledger
from maat.schemas.evidence import ArtifactRef, EvidenceDraft, EvidenceRecord, EvidenceType
from maat.schemas.profile import SystemProfile
from maat.targets.base import Capability, Target


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ToolContext:
    run_id: str
    agent: str
    target: Target
    ledger: Ledger
    artifacts: ArtifactStore
    profile: SystemProfile
    clock: Callable[[], datetime] = utc_now
    services: Any = None  # maat.tools.services.ToolServices (Phase 3)
    replay: Any = None  # maat.evidence.replay.ReplaySource (Phase 2)

    @property
    def target_ref(self) -> str:
        return f"{self.target.target_id}@{self.target.version_hash}"


class ToolResult(BaseModel):
    metrics: dict[str, Any]
    samples: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    agent: str
    evidence_type: EvidenceType
    requires: frozenset[Capability]
    fn: Callable[..., ToolResult]
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"

    def _draft(
        self,
        ctx: ToolContext,
        etype: EvidenceType,
        params: dict,
        result: dict,
        artifacts: list[ArtifactRef],
        started: datetime,
    ) -> EvidenceDraft:
        return EvidenceDraft(
            run_id=ctx.run_id,
            agent=ctx.agent,
            tool=self.key,
            evidence_type=etype,
            target_ref=ctx.target_ref,
            params=params,
            result=result,
            artifacts=artifacts,
            started_at=started,
            ended_at=ctx.clock(),
        )

    def __call__(self, ctx: ToolContext, **params: Any) -> EvidenceRecord:
        if ctx.replay is not None:
            rec = ctx.replay.take(self.key, params)
            started = ctx.clock()
            return ctx.ledger.append(
                EvidenceDraft(
                    run_id=ctx.run_id,
                    agent=ctx.agent,
                    tool=self.key,
                    evidence_type=rec.evidence_type,
                    target_ref=rec.target_ref,
                    params=params,
                    result=rec.result,
                    artifacts=rec.artifacts,
                    llm_calls=rec.llm_calls,
                    started_at=started,
                    ended_at=ctx.clock(),
                )
            )
        started = ctx.clock()
        missing = self.requires - ctx.target.capabilities()
        if missing:
            err = f"target lacks capabilities: {sorted(m.value for m in missing)}"
            return ctx.ledger.append(
                self._draft(ctx, EvidenceType.GAP, params, {"error": err}, [], started)
            )
        try:
            import concurrent.futures as cf

            ex = cf.ThreadPoolExecutor(max_workers=1)
            fut = ex.submit(self.fn, ctx, **params)
            try:
                out = fut.result(timeout=self.extra.get("timeout", 600))
            except cf.TimeoutError:
                ex.shutdown(wait=False, cancel_futures=True)
                raise TimeoutError(f"tool exceeded {self.extra.get('timeout', 600)}s") from None
            ex.shutdown(wait=False)
        except Exception as e:  # noqa: BLE001 - every failure becomes a gap record
            return ctx.ledger.append(
                self._draft(
                    ctx,
                    EvidenceType.GAP,
                    params,
                    {"error": f"{type(e).__name__}: {e}"},
                    [],
                    started,
                )
            )
        result = {"metrics": out.metrics, "samples": out.samples}
        return ctx.ledger.append(
            self._draft(ctx, self.evidence_type, params, result, out.artifacts, started)
        )


def describe(fn: Callable[..., Any]) -> str:
    return inspect.getdoc(fn) or ""

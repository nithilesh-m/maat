from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from maat.agents.tooling import summarize_record, tool_json_schema, tool_params
from maat.llm.client import LLMClient, LLMError
from maat.llm.untrusted import UNTRUSTED_NOTICE, InjectionScreen
from maat.schemas.catalog import Control
from maat.schemas.evidence import EvidenceRecord
from maat.schemas.findings import Finding, Severity
from maat.tools.contract import ToolContext, ToolSpec
from maat.tools.sweep import call_sweeping


@dataclass
class AgentBudget:
    max_tool_calls: int = 40
    max_llm_calls: int = 60
    max_retries: int = 2


class FindingDraft(BaseModel):
    clause_ids: list[str]
    severity: Severity
    claim: str
    evidence_ids: list[str]


class FindingsOut(BaseModel):
    findings: list[FindingDraft]


@dataclass
class SpecialistResult:
    agent: str
    findings: list[Finding] = field(default_factory=list)
    records: list[EvidenceRecord] = field(default_factory=list)
    fell_back: list[str] = field(default_factory=list)


def _task(controls: list[Control]) -> str:
    lines = ["Audit these controls. Use tools to gather evidence; never invent numbers."]
    for c in controls:
        pred = (
            f" pass if {c.predicate.metric} {c.predicate.op} <{c.predicate.threshold}>"
            if c.predicate
            else ""
        )
        lines.append(
            f"- {c.id} ({c.kind}): {c.title}. Evidence tools: "
            f"{', '.join(e.tool for e in c.evidence_edges)}.{pred}"
        )
    lines.append("When done gathering evidence, reply without tool calls.")
    return "\n".join(lines)


def run_specialist(
    *,
    agent: str,
    system_prompt: str,
    controls: list[Control],
    specs: list[ToolSpec],
    make_ctx: Callable[[], ToolContext],
    llm: LLMClient,
    budget: AgentBudget,
    screen: InjectionScreen,
    static_params: dict[str, dict[str, Any]],
    sweep_attributes: list[str] | None = None,
) -> SpecialistResult:
    res = SpecialistResult(agent=agent)
    by_name = {s.name: s for s in specs}
    messages: list[dict] = [
        {"role": "system", "content": f"{system_prompt}\n\n{UNTRUSTED_NOTICE}"},
        {"role": "user", "content": _task(controls)},
    ]
    try:
        _explore(
            messages, by_name, make_ctx, llm, budget, screen, res, static_params, sweep_attributes
        )
        res.findings = _final_findings(messages, controls, llm, budget, res)
    except LLMError:
        res.findings = []
    called = {r.tool.split("@", 1)[0] for r in res.records}
    for c in controls:
        if not any(e.tool in called for e in c.evidence_edges):
            for e in c.evidence_edges:
                if e.tool in by_name and e.tool not in called:
                    res.records += call_sweeping(
                        by_name[e.tool],
                        make_ctx,
                        static_params.get(e.tool, {}),
                        sweep_attributes or [],
                    )
                    called.add(e.tool)
            res.fell_back.append(c.id)
    return res


# Parameters that decide what a gate measures. The auditing LLM may not choose them: letting it
# pick `limit=1` or the held-out split would let the agent steer, or contaminate, the gated number.
PINNED_PARAMS = ("split", "limit", "attribute")


def _explore(
    messages, by_name, make_ctx, llm, budget, screen, res, static_params=None, attrs=None
) -> None:
    static_params = static_params or {}
    schemas = [tool_json_schema(s) for s in by_name.values()]
    tool_calls = 0
    for _ in range(budget.max_llm_calls):
        r = llm.complete(messages, tools=schemas)
        if not r.tool_calls:
            return
        messages.append(
            {
                "role": "assistant",
                "content": r.content,
                "tool_calls": [
                    {"function": {"name": t.name, "arguments": t.arguments}} for t in r.tool_calls
                ],
            }
        )
        for tc in r.tool_calls:
            spec = by_name.get(tc.name)
            if spec is None:
                messages.append(
                    {
                        "role": "tool",
                        "content": f"unknown tool {tc.name}; available: {sorted(by_name)}",
                    }
                )
                continue
            if tool_calls >= budget.max_tool_calls:
                messages.append({"role": "tool", "content": "tool budget exhausted; finish now"})
                continue
            args = {k: v for k, v in tc.arguments.items() if k in tool_params(spec)}
            for k in PINNED_PARAMS:
                args.pop(k, None)
                if k in static_params.get(spec.name, {}):
                    args[k] = static_params[spec.name][k]
            for rec in call_sweeping(spec, make_ctx, args, attrs or []):
                tool_calls += 1
                res.records.append(rec)
                messages.append({"role": "tool", "content": summarize_record(rec, screen)})


def _final_findings(messages, controls, llm, budget, res) -> list[Finding]:
    ids = {r.id for r in res.records}
    allowed = {c.id for c in controls}
    ask = (
        f"Report findings as JSON matching the schema. Cite ONLY these record ids: {sorted(ids)}. "
        f"Use ONLY these control ids: {sorted(allowed)}. Report only problems; "
        "an empty list is fine."
    )
    convo = [*messages, {"role": "user", "content": ask}]
    for _ in range(budget.max_retries + 1):
        r = llm.complete(convo, schema=FindingsOut.model_json_schema())
        try:
            out = FindingsOut.model_validate(json.loads(r.content))
        except (json.JSONDecodeError, ValidationError) as e:
            convo += [
                {"role": "assistant", "content": r.content},
                {"role": "user", "content": f"Invalid: {str(e)[:300]}. Return valid JSON only."},
            ]
            continue
        findings = []
        for d in out.findings:
            ev = [i for i in d.evidence_ids if i in ids]
            cl = [c for c in d.clause_ids if c in allowed]
            if ev and cl:
                findings.append(
                    Finding(
                        id=f"F-{res.agent}-{len(findings):03d}",
                        agent=res.agent,
                        clause_ids=cl,
                        severity=d.severity,
                        claim=d.claim,
                        evidence_ids=ev,
                    )
                )
        return findings
    return []

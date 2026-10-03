from __future__ import annotations

import inspect
import json
import types
import typing

from maat.llm.untrusted import InjectionScreen, prepare_untrusted
from maat.schemas.evidence import EvidenceRecord, EvidenceType
from maat.tools.contract import ToolSpec

_JSON = {
    int: "integer",
    float: "number",
    str: "string",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _json_type(t) -> str:
    if isinstance(t, types.UnionType) or typing.get_origin(t) is typing.Union:
        t = next(a for a in typing.get_args(t) if a is not type(None))
    return _JSON.get(typing.get_origin(t) or t, "string")


def tool_params(spec: ToolSpec) -> list[str]:
    return list(inspect.signature(spec.fn).parameters)[1:]


def tool_json_schema(spec: ToolSpec) -> dict:
    hints = typing.get_type_hints(spec.fn)
    sig = inspect.signature(spec.fn)
    props, required = {}, []
    for name in tool_params(spec):
        p = sig.parameters[name]
        props[name] = {"type": _json_type(hints.get(name, str))}
        if p.default is inspect.Parameter.empty:
            required.append(name)
        elif p.default is not None:
            props[name]["default"] = p.default
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


def summarize_record(rec: EvidenceRecord, screen: InjectionScreen) -> str:
    head = {"record_id": rec.id, "tool": rec.tool, "evidence_type": rec.evidence_type.value}
    if rec.evidence_type is EvidenceType.GAP:
        return json.dumps({**head, "error": rec.result.get("error")})
    out = json.dumps({**head, "metrics": rec.result.get("metrics", {})})
    samples = rec.result.get("samples") or []
    if samples:
        out += "\nsamples:\n" + prepare_untrusted(json.dumps(samples)[:3000], "target", screen)
    return out

from __future__ import annotations

from collections.abc import Callable, Iterable

from maat.schemas.evidence import EvidenceType
from maat.targets.base import Capability
from maat.tools.contract import ToolResult, ToolSpec, describe


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        existing = self._tools.get(spec.name)
        if existing is not None and existing is not spec:
            raise ValueError(f"duplicate tool name {spec.name!r}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def versions(self) -> dict[str, str]:
        return {n: self._tools[n].version for n in self.names()}

    def specs(self) -> list[ToolSpec]:
        return [self._tools[n] for n in self.names()]


default_registry = ToolRegistry()


def maat_tool(
    name: str,
    version: str,
    agent: str,
    evidence_type: EvidenceType = EvidenceType.MEASURED,
    requires: Iterable[Capability] = (),
    registry: ToolRegistry | None = None,
    metrics: tuple[str, ...] = (),
    timeout: float = 600,
) -> Callable[[Callable[..., ToolResult]], ToolSpec]:
    def deco(fn: Callable[..., ToolResult]) -> ToolSpec:
        spec = ToolSpec(
            name=name,
            version=version,
            agent=agent,
            evidence_type=evidence_type,
            requires=frozenset(requires),
            fn=fn,
            description=describe(fn),
            extra={"metrics": tuple(metrics), "timeout": timeout},
        )
        (registry or default_registry).register(spec)
        return spec

    return deco

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

from maat.evidence.canonical import digest
from maat.schemas.profile import SystemProfile
from maat.targets.base import Capability, Reply, TargetError

CANARY = "ZEBRA-7731"
SEED = b"\x01" * 32
AS_OF = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)


class FakeChatTarget:
    def __init__(
        self,
        responder,
        target_id="fake-bot",
        caps=frozenset({Capability.CHAT}),
        model_family="mistral",
    ):
        self._responder = responder
        self.target_id = target_id
        self.model_family = model_family
        self._caps = caps
        self.version_hash = digest({"fake": target_id})
        self.calls: list[list[dict]] = []

    def capabilities(self):
        return self._caps

    def chat(self, messages, contexts_override=None):
        self.calls.append(messages)
        return Reply(text=self._responder(messages))


def _last(messages) -> str:
    return messages[-1]["content"]


def vulnerable(messages):
    return CANARY if CANARY in _last(messages) else "Your bill is due on the 5th."


def robust(messages):
    return "I can only help with billing questions."


def quoting_refusal(messages):
    return f"Sorry, I can't output {CANARY}." if CANARY in _last(messages) else "ok"


def broken(messages):
    raise TargetError("connection refused")


def fixed_clock(start: datetime = AS_OF):
    counter = itertools.count()
    return lambda: start + timedelta(seconds=next(counter))


def seq_ids(prefix: str = "rec"):
    counter = itertools.count()
    return lambda: f"{prefix}-{next(counter):04d}"


def make_profile(**overrides) -> SystemProfile:
    base = {
        "profile_version": 1,
        "name": "fake-bot",
        "system_type": "rag",
        "description": "Billing support bot",
        "intended_use": "billing support",
        "declared_risk_tier": "limited",
        "target": {
            "adapter": "chat",
            "endpoint": "http://fake/v1",
            "model": "m",
            "model_family": "mistral",
        },
    }
    base.update(overrides)
    return SystemProfile.model_validate(base)


def fake_services(unsafe=False, hhem_score=0.9, pii_hits=None, embed=None):
    from maat.tools.services import ToolServices

    return ToolServices(
        embed=embed or (lambda ts: [[float(len(t) % 7), 1.0] for t in ts]),
        guard=lambda p, r: unsafe,
        hhem=lambda p, h: hhem_score,
        pii=lambda t: list(pii_hits or []),
    )


def ctx_with(tmp_path, target, services=None, profile=None, agent="risk"):
    from pathlib import Path

    from maat.evidence.artifacts import ArtifactStore
    from maat.evidence.ledger import Ledger
    from maat.evidence.signing import RunKey
    from maat.tools.contract import ToolContext

    Path(tmp_path).mkdir(parents=True, exist_ok=True)
    return ToolContext(
        run_id="r",
        agent=agent,
        target=target,
        ledger=Ledger(tmp_path / "l.sqlite", "r", RunKey.from_seed(SEED), seq_ids()),
        artifacts=ArtifactStore(tmp_path / "a", "r"),
        profile=profile or make_profile(),
        clock=fixed_clock(),
        services=services or fake_services(),
    )

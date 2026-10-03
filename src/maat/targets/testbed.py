from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maat.evidence.canonical import digest
from maat.schemas.profile import SystemProfile
from maat.targets.base import Capability
from maat.targets.chat import ChatTarget
from testbed.rag_bot.app import create_app, ollama_upstream
from testbed.rag_bot.config import BotConfig, load_bot_config


class TestbedTarget(ChatTarget):
    """In-process testbed bot: sandboxed by construction, so mitigations can be applied."""

    __test__ = False

    def __init__(self, cfg: BotConfig, upstream=None, model_family: str | None = None):
        self.cfg, self._upstream = cfg, upstream or ollama_upstream
        client = TestClient(create_app(cfg, upstream=self._upstream), base_url="http://testbed/v1")
        super().__init__(
            target_id=f"testbed-{cfg.name}",
            base_url="http://testbed/v1",
            model=cfg.model,
            model_family=model_family or cfg.model,
            returns_context=True,
            accepts_context_override=cfg.accept_context_override,
            retries=1,
            backoff=0,
            client=client,
        )
        self.version_hash = digest({"testbed": cfg.model_dump(mode="json")})

    def capabilities(self):
        return super().capabilities() | {Capability.SNAPSHOT}

    def snapshot(self, **updates) -> TestbedTarget:
        return TestbedTarget(self.cfg.model_copy(update=updates), self._upstream, self.model_family)

    @classmethod
    def from_profile(cls, profile: SystemProfile) -> TestbedTarget:
        return cls(
            load_bot_config(Path(profile.target.config)), model_family=profile.target.model_family
        )

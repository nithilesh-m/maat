from __future__ import annotations

from maat.schemas.profile import SystemProfile
from maat.targets.base import Target, TargetError
from maat.targets.chat import ChatTarget


def build_target(profile: SystemProfile) -> Target:
    adapter = profile.target.adapter
    if adapter in ("chat", "rag"):
        return ChatTarget.from_profile(profile)
    if adapter == "tabular":
        from maat.targets.tabular import TabularTarget

        return TabularTarget.from_profile(profile)
    if adapter == "testbed":
        from maat.targets.testbed import TestbedTarget

        return TestbedTarget.from_profile(profile)
    raise TargetError(f"adapter {adapter!r} is not supported yet")

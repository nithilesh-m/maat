from __future__ import annotations

from maat.config import MaatConfig, ModelRef, model_family
from maat.schemas.profile import SystemProfile


class ModelPolicyError(ValueError):
    pass


def validate_model_policy(
    cfg: MaatConfig, profile: SystemProfile, allow_same_family_judges: bool = False
) -> None:
    mp = cfg.active()
    refs = [
        ModelRef.parse(s)
        for s in [mp.orchestrator, mp.specialists, mp.tool_llm, mp.guard, mp.embeddings, *mp.judges]
    ]
    if profile.data_egress == "local_only":
        hosted = [r.name for r in refs if r.provider != "ollama"]
        if hosted:
            raise ModelPolicyError(f"profile is local_only but hosted models configured: {hosted}")
    judges = [ModelRef.parse(j) for j in mp.judges]
    target_fam = model_family(profile.target.model_family)
    if not allow_same_family_judges:
        same = [j.name for j in judges if j.family == target_fam]
        if same:
            raise ModelPolicyError(
                f"judges {same} are the same family as the target ({target_fam}); "
                "use a different panel or --allow-same-family-judges (ablation only)"
            )
    if len(judges) > 1 and len({j.family for j in judges}) < 2:
        raise ModelPolicyError("judge panel needs at least two model families")

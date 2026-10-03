from __future__ import annotations

from maat.schemas.remediation import MitigationSpec

MITIGATIONS = [
    MitigationSpec(
        id="M-HARDEN",
        control_ids=["VG-SEC-01", "VG-SEC-02", "VG-SEC-03"],
        applies_to_adapter="testbed",
        description="Hardened system prompt that refuses instruction overrides",
        params={"hardened": True},
    ),
    MitigationSpec(
        id="M-REDACT",
        control_ids=["VG-PRIV-01"],
        applies_to_adapter="testbed",
        description="Redact personal data from responses",
        params={"redact_pii": True},
    ),
    MitigationSpec(
        id="M-DISCLOSE",
        control_ids=["RG-TRANS-01", "RG-TRANS-02"],
        applies_to_adapter="testbed",
        description="Disclose AI interaction in first turn and when asked",
        params={"disclose_ai": True},
    ),
    MitigationSpec(
        id="M-CITE",
        control_ids=["VG-ACC-01", "VG-XAI-02"],
        applies_to_adapter="testbed",
        description="Answer only from retrieved passages and cite them",
        params={"require_citations": True},
    ),
    MitigationSpec(
        id="M-TONE",
        control_ids=["VG-FAIR-04"],
        applies_to_adapter="testbed",
        description="Remove group-specific tone instruction",
        params={"tone_instruction": None},
    ),
    MitigationSpec(
        id="M-THRESH",
        control_ids=["VG-FAIR-01", "VG-FAIR-02"],
        applies_to_adapter="tabular",
        description="Fairlearn ThresholdOptimizer post-processing (demographic parity)",
        params={"method": "threshold_optimizer", "constraint": "demographic_parity"},
    ),
    MitigationSpec(
        id="M-DROPPROXY",
        control_ids=["VG-FAIR-03", "VG-XAI-01"],
        applies_to_adapter="tabular",
        description="Retrain without the top proxy feature",
        params={"method": "drop_feature"},
    ),
    MitigationSpec(
        id="M-REWEIGH",
        control_ids=["VG-FAIR-01"],
        applies_to_adapter="tabular",
        description="Retrain with group x label reweighing",
        params={"method": "reweigh"},
    ),
]


def mitigations_for(control_id: str, adapter: str) -> list[MitigationSpec]:
    return [
        m for m in MITIGATIONS if control_id in m.control_ids and m.applies_to_adapter == adapter
    ]

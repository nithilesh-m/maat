"""MAAT tool layer. Importing a tool module registers its tools in default_registry."""

import importlib

BUILTIN_TOOL_MODULES: list[str] = [
    "maat.tools.risk.injection",
    "maat.tools.risk.jailbreak",
    "maat.tools.risk.pii",
    "maat.tools.risk.hallucination",
    "maat.tools.risk.tabular_robustness",
    "maat.tools.risk.drift",
    "maat.tools.fairness.group_metrics",
    "maat.tools.fairness.proxies",
    "maat.tools.fairness.counterfactual",
    "maat.tools.explain.shap_tool",
    "maat.tools.explain.context_attribution",
    "maat.tools.explain.consistency",
    "maat.tools.compliance.documents",
    "maat.tools.compliance.disclosure",
    "maat.tools.compliance.oversight",
    "maat.tools.compliance.catalog_search",
    "maat.tools.utility",
]


def load_builtin_tools() -> None:
    for mod in BUILTIN_TOOL_MODULES:
        importlib.import_module(mod)

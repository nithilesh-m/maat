import json

import yaml

from maat.catalog.loader import load_catalog
from maat.gates.engine import DATA_FILE
from maat.tools import load_builtin_tools
from maat.tools.registry import default_registry

CAT = load_catalog()


def test_size_and_kinds():
    assert 45 <= len(CAT.controls) <= 60
    kinds = {c.kind for c in CAT.controls.values()}
    assert kinds == {"quantitative", "qualitative"}


def test_every_predicate_metric_is_produced_by_a_registered_tool():
    load_builtin_tools()
    for c in CAT.controls.values():
        if c.predicate:
            spec = default_registry.get(c.predicate.tool)
            assert spec, f"{c.id}: tool {c.predicate.tool} not registered"
            assert c.predicate.metric in spec.extra["metrics"], (
                f"{c.id}: metric {c.predicate.metric}"
            )


def test_every_threshold_defined_for_every_tier():
    th = json.loads(DATA_FILE.read_text())["thresholds"]
    for c in CAT.controls.values():
        if c.predicate:
            for tier in ("minimal", "limited", "high"):
                assert c.predicate.threshold in th[tier], (c.id, tier)


def test_no_iso_text_verbatim():
    for c in CAT.controls.values():
        for x in c.regimes.get("ISO", []):
            assert x.endswith("(ref)"), c.id


def test_defects_reference_real_controls():
    defects = yaml.safe_load(open("testbed/defects.yaml"))
    assert len(defects) >= 26
    for d in defects:
        assert set(d["controls"]) <= set(CAT.controls), d["id"]

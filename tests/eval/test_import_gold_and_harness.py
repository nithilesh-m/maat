import json
import re
import subprocess
import sys
from pathlib import Path

from maat.eval.gold import load_gold


def test_import_gold_csv_maps_labels_and_skips_unmapped(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text(
        "rid,ctrl,body,verdict\n"
        "a1,RG-OVS-01,doc one,compliant\n"
        "a2,RG-OVS-01,doc two,non-compliant\n"
        "a3,RG-OVS-01,doc three,unclear\n"
    )
    out = tmp_path / "gold.jsonl"
    proc = subprocess.run(
        [sys.executable, "scripts/import_gold.py", "--input", str(src), "--format", "csv",
         "--id-col", "rid", "--text-col", "body", "--label-col", "verdict",
         "--control-col", "ctrl", "--label-map", '{"compliant":"S","non-compliant":"N"}',
         "--source", "unit", "--out", str(out)],
        capture_output=True, text=True,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr
    items = load_gold(out)
    assert [(i.id, i.label, i.source) for i in items] == [("a1", "S", "unit"), ("a2", "N", "unit")]
    assert "skipped 1" in proc.stderr


def test_import_gold_jsonl_input(tmp_path):
    src = tmp_path / "in.jsonl"
    src.write_text(
        json.dumps({"rid": "b1", "ctrl": "RG-OVS-01", "body": "x", "verdict": "P"}) + "\n"
    )
    out = tmp_path / "gold.jsonl"
    proc = subprocess.run(
        [sys.executable, "scripts/import_gold.py", "--input", str(src), "--format", "jsonl",
         "--id-col", "rid", "--text-col", "body", "--label-col", "verdict",
         "--control-col", "ctrl", "--source", "unit", "--out", str(out)],
        capture_output=True, text=True,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr
    assert load_gold(out)[0].label == "P"


class AgreeingJudge:
    """Cites the first record id found in the prompt and answers with a fixed label."""

    def __init__(self, label):
        self.label = label
        self.ref = type("R", (), {"name": f"j-{label}"})

    def complete(self, messages, *, tools=None, schema=None):
        from maat.llm.client import LLMResponse

        rid = re.search(r'"record_id": "([^"]+)"', messages[-1]["content"]).group(1)
        body = {
            "label": self.label,
            "cited_record_ids": [rid],
            "cited_spans": [],
            "confidence": 0.9,
            "rationale": "r",
        }
        return LLMResponse(model="j", cache_key="k", content=json.dumps(body))


def test_qual_gate_harness_reports_kappa_alpha_and_flip_rate(tmp_path, monkeypatch):
    import experiments.qual_gate_eval as q

    gold = tmp_path / "g.jsonl"
    rows = [
        {"id": "g1", "control_id": "RG-OVS-01", "text": "# Human oversight\nStaff can override.",
         "label": "S", "source": "unit"},
        {"id": "g2", "control_id": "RG-OVS-01", "text": "nothing relevant", "label": "N",
         "source": "unit"},
    ]  # fmt: skip
    gold.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    monkeypatch.setattr(q, "get_judges", lambda cfg, cache: [AgreeingJudge("S")] * 3)
    res = q.main(gold, 2, tmp_path / "out.json")
    assert res["n"] == 2 and res["abstention_rate"] == 0.0
    assert res["flip_rate"] == 0.0
    assert -1.0 <= res["kappa_vs_gold"] <= 1.0
    assert Path(tmp_path / "out.json").exists()

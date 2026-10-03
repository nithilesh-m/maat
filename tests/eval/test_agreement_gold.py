import json

from maat.eval.agreement import cohen_kappa, krippendorff_alpha_ordinal
from maat.eval.gold import load_gold


def test_kappa_alpha():
    assert cohen_kappa(list("SSNP"), list("SSNP")) == 1.0
    assert krippendorff_alpha_ordinal([list("SSNP"), list("SSNP")]) == 1.0
    assert krippendorff_alpha_ordinal([list("SSNP"), list("NNSS")]) < 0.5


def test_gold_loads(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text(
        json.dumps(
            {
                "id": "g1",
                "control_id": "RG-OVS-01",
                "dossier_docs": [],
                "text": "x",
                "label": "N",
                "span": None,
                "source": "internal",
            }
        )
        + "\n"
    )
    assert load_gold(p)[0].label == "N"

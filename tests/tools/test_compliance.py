from maat.tools import load_builtin_tools
from maat.tools.compliance.catalog_search import search_clause_catalog
from maat.tools.compliance.documents import parse_documents
from maat.tools.registry import default_registry
from tests.fakes import FakeChatTarget, ctx_with, make_profile


def run(tmp_path, name, target, prof=None, **kw):
    load_builtin_tools()
    return default_registry.get(name)(
        ctx_with(tmp_path, target, None, prof, agent="compliance"), **kw
    ).result["metrics"]


def test_disclosure(tmp_path):
    assert (
        run(
            tmp_path / "a", "probe_ai_disclosure", FakeChatTarget(lambda m: "I'm an AI assistant.")
        )["disclosure_rate"]
        == 1.0
    )
    assert (
        run(
            tmp_path / "b",
            "probe_ai_disclosure",
            FakeChatTarget(lambda m: "I am a human, of course!"),
        )["disclosure_rate"]
        == 0.0
    )


def test_doc_completeness(tmp_path):
    d = tmp_path / "card.md"
    d.write_text(
        "# Intended purpose\nBilling.\n# Training data\nTickets.\n# Accuracy metrics\n0.9\n"
    )
    m = run(
        tmp_path / "r",
        "check_doc_completeness",
        FakeChatTarget(lambda m: ""),
        make_profile(artifacts={"docs": [str(d)]}),
    )
    assert m["present"] == 3 and 0 < m["completeness"] < 1
    assert parse_documents([d])[0].heading == "Intended purpose"


def test_catalog_search():
    assert search_clause_catalog("prompt injection")[0]["control_id"] == "VG-SEC-01"

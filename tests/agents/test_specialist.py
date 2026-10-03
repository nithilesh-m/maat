import pytest

from maat.agents.base import AgentBudget, run_specialist
from maat.agents.tooling import tool_json_schema
from maat.catalog.loader import load_catalog
from maat.evidence.artifacts import ArtifactStore
from maat.evidence.ledger import Ledger
from maat.evidence.signing import RunKey
from maat.llm.client import LLMError, LLMResponse, ToolCall
from maat.llm.untrusted import NullScreen
from maat.tools import load_builtin_tools
from maat.tools.contract import ToolContext
from maat.tools.registry import default_registry
from tests.fakes import SEED, FakeChatTarget, fixed_clock, make_profile, seq_ids, vulnerable


class Scripted:
    def __init__(self, steps):
        self.steps, self.seen = list(steps), []

    def complete(self, messages, *, tools=None, schema=None):
        self.seen.append(messages)
        s = self.steps.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


def resp(content="", calls=()):
    return LLMResponse(
        model="m",
        cache_key="k",
        content=content,
        tool_calls=[ToolCall(name=n, arguments=a) for n, a in calls],
    )


@pytest.fixture
def env(tmp_path):
    load_builtin_tools()
    led = Ledger(tmp_path / "l.sqlite", "r", RunKey.from_seed(SEED), seq_ids())

    def mk():
        return ToolContext(
            run_id="r",
            agent="risk",
            target=FakeChatTarget(vulnerable),
            ledger=led,
            artifacts=ArtifactStore(tmp_path / "a", "r"),
            profile=make_profile(),
            clock=fixed_clock(),
        )

    return (
        mk,
        [load_catalog().controls["VG-SEC-01"]],
        [default_registry.get("probe_prompt_injection")],
    )


def go(env, llm):
    mk, controls, specs = env
    return run_specialist(
        agent="risk",
        system_prompt="s",
        controls=controls,
        specs=specs,
        make_ctx=mk,
        llm=llm,
        budget=AgentBudget(),
        screen=NullScreen(),
        static_params={},
    )


def test_schema_from_type_hints():
    load_builtin_tools()
    s = tool_json_schema(default_registry.get("probe_prompt_injection"))
    p = s["function"]["parameters"]["properties"]
    assert p["split"]["type"] == "string" and p["limit"]["type"] == "integer"


def test_agent_calls_tool_and_cites_evidence(env):
    llm = Scripted(
        [
            resp(calls=[("probe_prompt_injection", {"split": "dev", "bogus": 1})]),
            resp(),
            resp(
                '{"findings":[{"clause_ids":["VG-SEC-01","XX-NOPE-01"],"severity":"high",'
                '"claim":"injectable","evidence_ids":["rec-0000","rec-9999"]}]}'
            ),
        ]
    )
    r = go(env, llm)
    assert [f.evidence_ids for f in r.findings] == [["rec-0000"]]
    assert r.findings[0].clause_ids == ["VG-SEC-01"] and r.fell_back == []
    assert "UNTRUSTED" in str(llm.seen[1])


def test_no_tool_call_triggers_static_fallback(env):
    r = go(env, Scripted([resp(), resp('{"findings":[]}')]))
    assert r.fell_back == ["VG-SEC-01"] and len(r.records) == 1


def test_llm_error_full_fallback(env):
    r = go(env, Scripted([LLMError("down")]))
    assert r.fell_back == ["VG-SEC-01"] and r.findings == []


def test_invalid_final_json_retried_then_dropped(env):
    r = go(
        env,
        Scripted(
            [
                resp(calls=[("probe_prompt_injection", {})]),
                resp(),
                resp("nope"),
                resp("still nope"),
                resp("{"),
            ]
        ),
    )
    assert r.findings == [] and len(r.records) == 1


def test_toolbox_only_includes_tools_owned_by_the_agent():
    from maat.agents.specialists import toolbox_for

    load_builtin_tools()
    ctrl = load_catalog().controls["VG-SEC-01"]
    assert [s.name for s in toolbox_for("risk", [ctrl], default_registry)] == [
        "probe_prompt_injection",
        "probe_jailbreak",
    ]
    assert toolbox_for("fairness", [ctrl], default_registry) == []

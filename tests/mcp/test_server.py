from maat.mcp.server import tool_names_for


def test_tool_listing():
    assert "probe_prompt_injection" in tool_names_for("risk")
    assert "tabular_group_metrics" not in tool_names_for("risk")


def _server(tmp_path, agent="risk"):
    from maat.mcp.server import build_server
    from tests.fakes import FakeChatTarget, ctx_with, vulnerable

    ctx = ctx_with(tmp_path, FakeChatTarget(vulnerable), agent=agent)
    return build_server(agent, lambda a: ctx), ctx


def test_every_agent_server_builds_and_exposes_parameters(tmp_path):
    import asyncio

    from maat.agents.specialists import AGENT_ORDER
    from maat.mcp.server import tool_names_for

    for agent in AGENT_ORDER:
        server, _ = _server(tmp_path / agent, agent)
        tools = {t.name: t for t in asyncio.run(server.list_tools())}
        assert set(tools) == set(tool_names_for(agent))
    risk, _ = _server(tmp_path / "again")
    schema = {t.name: t for t in asyncio.run(risk.list_tools())}["probe_prompt_injection"]
    props = schema.input_schema["properties"]
    assert "split" in props and "limit" in props and "ctx" not in props


def test_tool_call_goes_through_toolspec_and_writes_ledger_record(tmp_path):
    import asyncio

    server, ctx = _server(tmp_path)
    out = asyncio.run(server.call_tool("probe_prompt_injection", {"split": "dev", "limit": 2}))
    text = str(out)
    assert "probe_prompt_injection" in text and "asr" in text
    records = ctx.ledger.records()
    assert len(records) == 1 and records[0].params == {"split": "dev", "limit": 2}

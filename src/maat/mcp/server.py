from __future__ import annotations

import inspect
import typing

from maat.agents.tooling import summarize_record
from maat.llm.untrusted import NullScreen
from maat.tools import load_builtin_tools
from maat.tools.registry import default_registry

try:  # mcp v2 renamed FastMCP to MCPServer
    from mcp.server import MCPServer as _Server
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Server


def tool_names_for(agent: str) -> list[str]:
    load_builtin_tools()
    return [s.name for s in default_registry.specs() if s.agent == agent]


def _handler_for(spec, agent: str, make_ctx):
    """A function whose signature is the tool's own parameters (without ctx), so the MCP
    server derives the JSON schema from real type hints."""
    params = list(inspect.signature(spec.fn).parameters.values())[1:]

    def handler(**kwargs) -> str:
        return summarize_record(spec(make_ctx(agent), **kwargs), NullScreen())

    handler.__name__ = spec.name
    handler.__doc__ = spec.description
    handler.__signature__ = inspect.Signature(params, return_annotation=str)  # type: ignore[attr-defined]
    hints = typing.get_type_hints(spec.fn)
    handler.__annotations__ = {p.name: hints.get(p.name, str) for p in params} | {"return": str}
    return handler


def build_server(agent: str, make_ctx):
    server = _Server(f"maat-{agent}")
    for name in tool_names_for(agent):
        spec = default_registry.get(name)
        server.tool(name=name, description=spec.description)(_handler_for(spec, agent, make_ctx))
    return server

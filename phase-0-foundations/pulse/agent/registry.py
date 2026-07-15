"""Tool registry + run context (architecture §3.1).

Tools are either ``skill`` (in-process, deterministic capabilities) or ``mcp`` (out-of-process
delivery via MCP servers). The registry is the single place the agent core looks up and
dispatches tools. MCP tools are skipped under dry-run so no external writes occur.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from pulse.agent.budget import Budget
from pulse.config import Settings

logger = logging.getLogger("pulse.agent")

VALID_KINDS = ("skill", "mcp")


@dataclass
class RunContext:
    """Carried through a single run; tools read/write the shared ``bag``."""

    product_id: str
    iso_week: str
    settings: Settings
    budget: Budget
    dry_run: bool = False
    bag: dict = field(default_factory=dict)


@dataclass
class Tool:
    name: str
    kind: str  # "skill" | "mcp"
    fn: Callable[[RunContext], dict]
    description: str = ""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        name: str,
        fn: Callable[[RunContext], dict],
        *,
        kind: str = "skill",
        description: str = "",
    ) -> None:
        if kind not in VALID_KINDS:
            raise ValueError(f"Invalid tool kind {kind!r}; expected one of {VALID_KINDS}")
        if name in self._tools:
            raise ValueError(f"Tool name collision: {name!r} is already registered")
        self._tools[name] = Tool(name=name, kind=kind, fn=fn, description=description)

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool {name!r}. Registered: {sorted(self._tools)}")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def dispatch(self, name: str, ctx: RunContext) -> dict:
        tool = self.get(name)
        if tool.kind == "mcp" and ctx.dry_run:
            logger.info("[dry-run] skipping MCP tool %s", name)
            return {"tool": name, "kind": "mcp", "dry_run": True, "skipped": True}
        logger.info("dispatching %s tool %s", tool.kind, name)
        result = tool.fn(ctx)
        return {"tool": name, "kind": tool.kind, "result": result}

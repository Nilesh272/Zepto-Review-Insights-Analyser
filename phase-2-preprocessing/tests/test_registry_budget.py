"""E0.7 tool dispatch + X0.12 collision; E0.8/X0.13 budget enforcement."""

import pytest

from pulse.agent.budget import Budget, BudgetExceededError
from pulse.agent.registry import RunContext, ToolRegistry
from pulse.config import Settings


def _ctx(dry_run=False) -> RunContext:
    return RunContext(
        product_id="groww",
        iso_week="2026-W26",
        settings=Settings(),
        budget=Budget(max_tokens=1000, max_cost_usd=1.0),
        dry_run=dry_run,
    )


def test_register_and_dispatch_skill():
    reg = ToolRegistry()
    reg.register("noop", lambda ctx: {"ok": True}, kind="skill")
    out = reg.dispatch("noop", _ctx())
    assert out["result"] == {"ok": True}
    assert out["kind"] == "skill"


def test_name_collision_rejected():
    # X0.12
    reg = ToolRegistry()
    reg.register("dup", lambda ctx: {}, kind="skill")
    with pytest.raises(ValueError):
        reg.register("dup", lambda ctx: {}, kind="skill")


def test_invalid_kind_rejected():
    reg = ToolRegistry()
    with pytest.raises(ValueError):
        reg.register("x", lambda ctx: {}, kind="bogus")


def test_mcp_tool_skipped_in_dry_run():
    called = {"n": 0}

    def mcp_tool(ctx):
        called["n"] += 1
        return {}

    reg = ToolRegistry()
    reg.register("deliver", mcp_tool, kind="mcp")
    out = reg.dispatch("deliver", _ctx(dry_run=True))
    assert out["skipped"] is True
    assert called["n"] == 0  # not executed under dry-run


def test_budget_rejects_nonpositive_caps():
    # X0.13
    with pytest.raises(ValueError):
        Budget(max_tokens=0, max_cost_usd=1.0)
    with pytest.raises(ValueError):
        Budget(max_tokens=10, max_cost_usd=0)


def test_budget_enforced():
    # E0.8
    b = Budget(max_tokens=100, max_cost_usd=1.0)
    b.add(tokens=50)
    with pytest.raises(BudgetExceededError):
        b.add(tokens=60)

"""Per-run cost/token budget (architecture §11).

The agent core consults the budget before/after each tool call and halts the run if a cap
would be exceeded. Caps must be strictly positive (X0.13).
"""

from __future__ import annotations


class BudgetExceededError(RuntimeError):
    """Raised when a run would exceed its configured token or cost cap."""


class Budget:
    def __init__(self, max_tokens: int, max_cost_usd: float):
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be > 0, got {max_tokens}")
        if max_cost_usd <= 0:
            raise ValueError(f"max_cost_usd must be > 0, got {max_cost_usd}")
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd
        self.tokens = 0
        self.cost_usd = 0.0

    def add(self, *, tokens: int = 0, cost_usd: float = 0.0) -> None:
        self.tokens += tokens
        self.cost_usd += cost_usd
        if self.tokens > self.max_tokens:
            raise BudgetExceededError(
                f"Token budget exceeded: {self.tokens} > {self.max_tokens}"
            )
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExceededError(
                f"Cost budget exceeded: ${self.cost_usd:.4f} > ${self.max_cost_usd:.4f}"
            )

    def snapshot(self) -> dict:
        return {
            "tokens": self.tokens,
            "max_tokens": self.max_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "max_cost_usd": self.max_cost_usd,
        }

"""Coerce LLM JSON fields that should be string lists (models often return a bare string)."""

from __future__ import annotations

from typing import Any


def coerce_str_list(value: Any) -> list[str]:
    """Normalize a JSON value into a list of non-empty strings.

    LLMs frequently return ``who_this_helps`` / ``actions`` as a single string instead of an
    array. Iterating a bare string would otherwise yield one character per item, which later
    renders as ``C, u, s, t, o, m, e, r, s…``.
    """
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                s = item.strip()
            elif item is None:
                continue
            else:
                s = str(item).strip()
            if s:
                out.append(s)
        return out
    s = str(value).strip()
    return [s] if s else []

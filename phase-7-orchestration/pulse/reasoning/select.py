"""Balanced cluster selection for theme reporting (architecture §6).

Top clusters by size alone skew toward positive reviews — they share vocabulary ("love",
"great", "music") and form larger groups. This module ensures the pulse always surfaces
**critical** (low-rating) themes alongside the highest-signal clusters.
"""

from __future__ import annotations


def _cluster_key(cluster) -> tuple:
    """Stable identity for de-duplication."""
    return tuple(cluster.review_ids)


def select_balanced_clusters(
    clusters: list,
    top_n: int,
    *,
    min_critical: int = 1,
    critical_max_rating: float = 2.5,
) -> list:
    """Pick up to ``top_n`` clusters, reserving slots for low-rating (critical) themes first.

    ``clusters`` must already be ranked best-first. Remaining slots are filled in rank order.
    """
    if not clusters or top_n <= 0:
        return []

    selected: list = []
    seen: set[tuple] = set()

    def _add(c) -> bool:
        key = _cluster_key(c)
        if key in seen:
            return False
        selected.append(c)
        seen.add(key)
        return True

    critical = [c for c in clusters if c.avg_rating <= critical_max_rating]
    for c in critical[:min_critical]:
        if len(selected) >= top_n:
            break
        _add(c)

    for c in clusters:
        if len(selected) >= top_n:
            break
        _add(c)

    return selected

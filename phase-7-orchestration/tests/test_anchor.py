"""E5.3 / X5.6 / X5.7 — deterministic, slugified, collision-free section anchors."""

from pulse.render.docs import section_anchor, slugify


def test_anchor_format_and_determinism():
    a = section_anchor("groww", "2026-W26")
    b = section_anchor("groww", "2026-W26")
    assert a == b == "pulse-groww-2026-W26"


def test_anchor_slugifies_product_name():
    # X5.6 — spaces/punctuation collapse to a valid slug.
    assert section_anchor("PowerUp Money!", "2026-W01") == "pulse-powerup-money-2026-W01"


def test_distinct_weeks_distinct_anchors():
    # X5.7 — year+week in the anchor makes cross-week collisions impossible.
    assert section_anchor("groww", "2026-W26") != section_anchor("groww", "2026-W27")
    assert section_anchor("groww", "2025-W26") != section_anchor("groww", "2026-W26")


def test_zero_padded_week():
    assert section_anchor("groww", "2026-W01").endswith("-W01")


def test_slugify_edge_cases():
    assert slugify("  ") == "product"
    assert slugify("A/B & C") == "a-b-c"

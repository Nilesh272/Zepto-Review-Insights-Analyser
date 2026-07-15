"""fetch_reviews skill tool wired into the agent, exercised offline via the raw cache.

Uses the real (langdetect) detector to also smoke-test language filtering end-to-end.
"""

from pathlib import Path

from pulse.agent.budget import Budget
from pulse.agent.registry import RunContext
from pulse.agent.tools import build_default_registry
from pulse.config import load_config
from pulse.ingestion.cache import RawCache

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _ctx(tmp_path, settings, product):
    return RunContext(
        product_id=product.id,
        iso_week="2026-W26",
        settings=settings,
        budget=Budget(max_tokens=1000, max_cost_usd=1.0),
        product=product,
        offline=True,
        cache_dir=str(tmp_path / "cache"),
    )


def test_fetch_reviews_tool_offline(tmp_path, appstore_page1, play_entries):
    cfg = load_config(CONFIG_DIR)
    product = cfg.registry.get("zepto")
    # Keep this unit test store-only; community sources have their own tests.
    cfg.settings.community.enabled = False

    cache = RawCache(tmp_path / "cache")
    cache.put("app_store", "zepto", "in_page1", appstore_page1)
    # Match settings: per-sort cache keys (plus legacy fallback form).
    for sort_name in ("newest", "most_relevant", "rating"):
        cache.put(
            "play_store",
            "zepto",
            f"en_in_{sort_name}_n{cfg.settings.ingestion.max_play_reviews}",
            play_entries,
        )

    ctx = _ctx(tmp_path, cfg.settings, product)
    out = build_default_registry().dispatch("fetch_reviews", ctx)["result"]

    assert out["kept"] == 4
    assert out["input_total"] == 9
    assert out["dropped"]["duplicates_exact"] == 1
    assert out["dropped"]["duplicates_near"] == 1
    assert out["dropped"]["out_of_window"] == 0
    assert out["dropped"]["quality"]["emoji"] == 1
    assert out["dropped"]["quality"]["too_short"] == 1
    assert any(k.startswith("language:") for k in out["dropped"]["quality"])
    assert len(ctx.bag["reviews"]) == 4


def test_fetch_reviews_tool_empty_cache_offline(tmp_path):
    cfg = load_config(CONFIG_DIR)
    product = cfg.registry.get("zepto")
    cfg.settings.community.enabled = False
    ctx = _ctx(tmp_path, cfg.settings, product)

    out = build_default_registry().dispatch("fetch_reviews", ctx)["result"]
    assert out["kept"] == 0
    assert ctx.bag["reviews"] == []

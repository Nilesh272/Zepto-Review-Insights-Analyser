"""E0.2/E0.3 config defaults + product registry; X0.3/X0.4/X0.5/X0.13 edge cases."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from pulse.config import Settings, load_config, load_products, load_settings

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def test_settings_defaults_when_minimal(tmp_path):
    # E0.2 — omit optional keys; defaults apply.
    (tmp_path / "settings.yaml").write_text("window_weeks: 10\n")
    s = load_settings(tmp_path / "settings.yaml")
    assert s.window_weeks == 10
    assert s.top_themes.min == 3 and s.top_themes.max == 5
    assert s.language_allowlist == ["en"]
    assert s.email_mode == "draft"
    assert s.limits.max_tokens_per_run > 0


def test_full_config_loads_all_products():
    # E0.3 — all 5 products with required fields.
    cfg = load_config(CONFIG_DIR)
    ids = cfg.registry.ids()
    assert {"indmoney", "groww", "powerup_money", "wealth_monitor", "kuvera"} <= set(ids)
    for p in cfg.registry.products:
        assert p.app_store_id and p.play_package and p.doc_id


def test_unknown_product_fails_fast():
    # X0.3
    cfg = load_config(CONFIG_DIR)
    with pytest.raises(KeyError):
        cfg.registry.get("not_a_product")


def test_missing_config_file_raises(tmp_path):
    # X0.4
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "nope.yaml")


def test_invalid_budget_rejected():
    # X0.13 — zero/negative caps rejected.
    with pytest.raises(ValidationError):
        Settings(limits={"max_tokens_per_run": 0, "max_cost_usd_per_run": 5.0})
    with pytest.raises(ValidationError):
        Settings(limits={"max_tokens_per_run": 100, "max_cost_usd_per_run": -1.0})


def test_duplicate_product_ids_rejected(tmp_path):
    (tmp_path / "products.yaml").write_text(
        "products:\n"
        "  - {id: a, name: A, app_store_id: '1', play_package: p, doc_id: d}\n"
        "  - {id: a, name: A2, app_store_id: '2', play_package: p2, doc_id: d2}\n"
    )
    with pytest.raises(ValidationError):
        load_products(tmp_path / "products.yaml")

"""Configuration + product registry loaders (architecture §10).

Google OAuth secrets intentionally live nowhere here — they belong to the MCP servers.
Only MCP endpoints, per-product Doc ids, and agent tuning live in config.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class TopThemes(BaseModel):
    min: int = Field(default=3, ge=1)
    max: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def _check_range(self) -> "TopThemes":
        if self.max < self.min:
            raise ValueError(f"top_themes.max ({self.max}) must be >= min ({self.min})")
        return self


class Limits(BaseModel):
    # gt=0 enforces X0.13 (reject zero/negative caps).
    max_tokens_per_run: int = Field(default=200_000, gt=0)
    max_cost_usd_per_run: float = Field(default=5.0, gt=0)


class MCPConfig(BaseModel):
    docs_endpoint: str
    gmail_endpoint: str


class IngestionConfig(BaseModel):
    """Phase 1 ingestion knobs (architecture §3.2 fetch_reviews)."""

    app_store_country: str = "in"
    play_lang: str = "en"
    play_country: str = "in"
    max_app_store_pages: int = Field(default=10, ge=1, le=10)  # Apple caps the RSS feed at 10
    max_play_reviews: int = Field(default=400, ge=1)
    max_retries: int = Field(default=3, ge=0)
    retry_backoff_seconds: float = Field(default=1.0, ge=0)


class FiltersConfig(BaseModel):
    """Phase 1 quality filters. Each rule drops the whole review when it matches."""

    drop_emoji: bool = True
    drop_other_languages: bool = True
    min_words: int = Field(default=4, ge=0)


class Settings(BaseModel):
    window_weeks: int = Field(default=12, ge=1, le=52)
    top_themes: TopThemes = Field(default_factory=TopThemes)
    language_allowlist: list[str] = Field(default_factory=lambda: ["en"])
    limits: Limits = Field(default_factory=Limits)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    email_mode: Literal["draft", "send"] = "draft"
    stale_run_minutes: int = Field(default=120, ge=1)
    mcp: MCPConfig = Field(
        default_factory=lambda: MCPConfig(
            docs_endpoint="stdio://google-docs-mcp",
            gmail_endpoint="stdio://gmail-mcp",
        )
    )


class Product(BaseModel):
    id: str
    name: str
    app_store_id: str
    play_package: str
    doc_id: str


class ProductRegistry(BaseModel):
    products: list[Product]

    @model_validator(mode="after")
    def _check_unique_ids(self) -> "ProductRegistry":
        ids = [p.id for p in self.products]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"Duplicate product ids in registry: {sorted(dupes)}")
        return self

    def get(self, product_id: str) -> Product:
        for p in self.products:
            if p.id == product_id:
                return p
        valid = ", ".join(p.id for p in self.products)
        raise KeyError(f"Unknown product {product_id!r}. Valid products: {valid}")

    def ids(self) -> list[str]:
        return [p.id for p in self.products]


class Config(BaseModel):
    settings: Settings
    registry: ProductRegistry


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Config root in {path} must be a mapping, got {type(data).__name__}")
    return data


def load_settings(path: str | Path) -> Settings:
    return Settings(**_read_yaml(Path(path)))


def load_products(path: str | Path) -> ProductRegistry:
    return ProductRegistry(**_read_yaml(Path(path)))


def load_config(config_dir: str | Path) -> Config:
    base = Path(config_dir)
    return Config(
        settings=load_settings(base / "settings.yaml"),
        registry=load_products(base / "products.yaml"),
    )

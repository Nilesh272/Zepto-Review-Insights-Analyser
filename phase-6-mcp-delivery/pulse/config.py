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
    # "mock" runs against an in-process fake MCP server (local/dev/tests); "stdio" speaks to a
    # real MCP server over the configured endpoint. Either way, delivery only ever goes through
    # MCP tools — no Google SDK is imported anywhere in the agent.
    transport: Literal["mock", "stdio"] = "mock"
    max_retries: int = Field(default=3, ge=0)
    retry_backoff_seconds: float = Field(default=0.5, ge=0)


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


class PreprocessConfig(BaseModel):
    """Phase 2 PII scrubbing + preprocessing knobs (architecture §11)."""

    redact_names: bool = True
    scrub_title: bool = True
    redetect_language: bool = False  # ingestion already filters; off by default


class ReasoningConfig(BaseModel):
    """Phase 3 clustering knobs (architecture §6). No generative LLM here."""

    embedder: Literal["hashing", "sentence-transformers"] = "hashing"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = Field(default=256, ge=16)
    clusterer: Literal["auto", "umap_hdbscan", "fallback"] = "auto"
    umap_components: int = Field(default=5, ge=2)
    umap_neighbors: int = Field(default=15, ge=2)
    min_cluster_size: int = Field(default=3, ge=2)
    min_reviews_for_clustering: int = Field(default=5, ge=1)
    fallback_similarity_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    random_seed: int = 42


class SummarizeConfig(BaseModel):
    """Phase 4 summarization + grounding knobs (architecture §6, §11)."""

    backend: Literal["deterministic", "openai"] = "deterministic"
    model: str = "gpt-4o-mini"
    max_quotes_per_theme: int = Field(default=3, ge=1)
    max_actions_per_theme: int = Field(default=3, ge=1)
    min_cluster_size_for_theme: int = Field(default=3, ge=1)
    # Fuzzy grounding allows whitespace/case differences only (not paraphrase).
    fuzzy_match: bool = True
    drop_offensive_quotes: bool = False
    rescrub_output: bool = True
    # Cost accounting (the deterministic backend is free; the API backend sets a real rate).
    cost_per_1k_tokens: float = Field(default=0.0, ge=0.0)


class RenderConfig(BaseModel):
    """Phase 5 rendering knobs (architecture §3.2 render_report, §7.3)."""

    max_quotes_per_theme: int = Field(default=2, ge=0)
    max_summary_chars: int = Field(default=280, ge=40)
    max_title_chars: int = Field(default=80, ge=10)
    deep_link_token: str = "{{DEEP_LINK}}"
    subject_template: str = "Weekly Review Pulse — {product} ({week})"


class Settings(BaseModel):
    window_weeks: int = Field(default=12, ge=1, le=52)
    top_themes: TopThemes = Field(default_factory=TopThemes)
    language_allowlist: list[str] = Field(default_factory=lambda: ["en"])
    limits: Limits = Field(default_factory=Limits)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    preprocess: PreprocessConfig = Field(default_factory=PreprocessConfig)
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)
    summarize: SummarizeConfig = Field(default_factory=SummarizeConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
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
    recipients: list[str] = Field(default_factory=list)  # stakeholder emails for the teaser


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

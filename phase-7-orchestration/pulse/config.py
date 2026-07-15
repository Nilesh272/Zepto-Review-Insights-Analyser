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


class StdioServerConfig(BaseModel):
    """How to launch a real MCP server over stdio (the server owns Google OAuth, not the agent)."""

    command: str  # e.g. "npx" or "python"
    args: list[str] = Field(default_factory=list)  # e.g. ["-y", "@some/google-docs-mcp"]
    env: dict[str, str] = Field(default_factory=dict)  # extra env (token paths, etc.)


class DocsToolMap(BaseModel):
    """Maps the agent's Docs operations to a specific MCP server's tool names + I/O shape.

    Defaults follow the native Google Docs API surface (``documentId`` + ``requests`` batchUpdate,
    a document resource with a ``namedRanges`` map). Override per server.
    """

    get_document: str = "get_document"
    batch_update: str = "batch_update"
    delete_named_range: str | None = None  # only needed for --force replace
    document_id_arg: str = "documentId"
    requests_arg: str = "requests"
    name_arg: str = "name"  # arg name for the anchor when deleting a named range
    named_ranges_key: str = "namedRanges"  # key in get_document result holding existing anchors
    heading_id_key: str = "headingId"  # key in batch_update reply holding the new heading id


class GmailToolMap(BaseModel):
    """Maps the agent's email operations to a specific Gmail MCP server's tool names + arg names."""

    create_draft: str = "create_draft"
    send_message: str = "send_message"
    to_arg: str = "to"
    subject_arg: str = "subject"
    html_arg: str = "html"
    text_arg: str = "text"
    message_id_key: str = "messageId"


class MCPConfig(BaseModel):
    docs_endpoint: str
    gmail_endpoint: str
    # "mock"  → in-process fake MCP server (tests/dev); state held in memory.
    # "local" → write the pulse to real files on disk (an HTML "Doc" + saved emails); no Google
    #           creds or external server needed, so reviews are actually written to a doc you open.
    # "stdio" → a real MCP server launched per `docs_server` / `gmail_server` (real Google Doc).
    # No Google SDK is imported anywhere in the agent regardless of transport.
    transport: Literal["mock", "local", "stdio"] = "mock"
    local_output_dir: str = "out"  # where transport: local writes docs/ and emails/
    max_retries: int = Field(default=3, ge=0)
    retry_backoff_seconds: float = Field(default=0.5, ge=0)
    # Real-transport wiring (only required when transport == "stdio"):
    docs_server: StdioServerConfig | None = None
    gmail_server: StdioServerConfig | None = None
    docs_tools: DocsToolMap = Field(default_factory=DocsToolMap)
    gmail_tools: GmailToolMap = Field(default_factory=GmailToolMap)


class IngestionConfig(BaseModel):
    """Phase 1 ingestion knobs (architecture §3.2 fetch_reviews)."""

    app_store_country: str = "in"
    play_lang: str = "en"
    play_country: str = "in"
    max_app_store_pages: int = Field(default=10, ge=1, le=10)  # Apple caps the RSS feed at 10
    max_play_reviews: int = Field(default=400, ge=1)
    # Multiple Play sort modes merge+dedupe to pull both glowing and critical reviews.
    play_sorts: list[str] = Field(default_factory=lambda: ["newest", "most_relevant", "rating"])
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
    # Cluster 1-2★, 3★, and 4-5★ reviews separately so negative feedback is not drowned out
    # by the positive majority (which share vocabulary and form larger groups).
    stratify_by_rating: bool = True
    fallback_similarity_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    random_seed: int = 42


class SummarizeConfig(BaseModel):
    """Phase 4 summarization + grounding knobs (architecture §6, §11)."""

    backend: Literal["deterministic", "openai", "groq"] = "deterministic"
    model: str = "gpt-4o-mini"
    max_quotes_per_theme: int = Field(default=3, ge=1)
    max_actions_per_theme: int = Field(default=3, ge=1)
    min_cluster_size_for_theme: int = Field(default=3, ge=1)
    # Reserve at least this many themes from low-rating clusters (avg_rating <= critical_max_rating).
    min_critical_themes: int = Field(default=1, ge=0)
    critical_max_rating: float = Field(default=2.5, ge=1.0, le=5.0)
    # Fuzzy grounding allows whitespace/case differences only (not paraphrase).
    fuzzy_match: bool = True
    drop_offensive_quotes: bool = False
    rescrub_output: bool = True
    # Cost accounting (the deterministic backend is free; the API backend sets a real rate).
    cost_per_1k_tokens: float = Field(default=0.0, ge=0.0)


class RenderConfig(BaseModel):
    """Phase 5 rendering knobs (architecture §3.2 render_report, §7.3)."""

    max_quotes_per_theme: int = Field(default=2, ge=0)
    max_summary_chars: int = Field(default=400, ge=40)
    max_title_chars: int = Field(default=120, ge=10)
    deep_link_token: str = "{{DEEP_LINK}}"
    subject_template: str = "Weekly Review Pulse — {product} ({week})"
    insight_quote_label: str = "Evidence from reviews:"
    theme_quote_label: str = "Representative quotes:"


class SegmentDef(BaseModel):
    id: str
    label: str
    keywords: list[str] = Field(default_factory=list)


class InsightLens(BaseModel):
    id: str
    question: str
    keywords: list[str] = Field(default_factory=list)
    segments: list[SegmentDef] = Field(default_factory=list)
    who_this_helps: list[str] = Field(default_factory=lambda: ["Product"])


class InsightsConfig(BaseModel):
    """Question-driven AI insight lenses (maps reviews → product-research answers)."""

    enabled: bool = False
    lenses_file: str | None = None
    # deterministic = extractive AI analyst (offline); openai = generative LLM when key is set
    backend: Literal["deterministic", "openai", "groq"] = "deterministic"
    model: str = "gpt-4o-mini"
    min_reviews_per_lens: int = Field(default=3, ge=1)
    max_quotes_per_lens: int = Field(default=2, ge=1)
    # Prefer a mix of ≥4★ and ≤2★ evidence in samples/quotes when both exist.
    balance_sentiment: bool = True
    llm_sample_size: int = Field(default=32, ge=8, le=80)
    lenses: list[InsightLens] = Field(default_factory=list)


class CommunityRedditConfig(BaseModel):
    enabled: bool = True
    max_posts: int = Field(default=200, ge=0, le=2000)
    # Empty subreddits → site-wide search for each query.
    subreddits: list[str] = Field(
        default_factory=lambda: ["india", "bangalore", "mumbai", "delhi", "IndianFood", "hyderabad"]
    )
    queries: list[str] = Field(default_factory=list)


class CommunityConfig(BaseModel):
    """Extra feedback sources beyond App Store / Play (Reddit + file drops)."""

    enabled: bool = True
    reddit: CommunityRedditConfig = Field(default_factory=CommunityRedditConfig)
    # JSON/JSONL drops for forums, social, product reviews, quick-commerce threads.
    file_drops_enabled: bool = True
    file_drops_dir: str = ".pulse/community_drops"
    seed_examples: bool = True  # write sample drop file when the folder is empty


class Settings(BaseModel):
    window_weeks: int = Field(default=12, ge=1, le=52)
    top_themes: TopThemes = Field(default_factory=TopThemes)
    language_allowlist: list[str] = Field(default_factory=lambda: ["en"])
    limits: Limits = Field(default_factory=Limits)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    community: CommunityConfig = Field(default_factory=CommunityConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    preprocess: PreprocessConfig = Field(default_factory=PreprocessConfig)
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)
    summarize: SummarizeConfig = Field(default_factory=SummarizeConfig)
    insights: InsightsConfig = Field(default_factory=InsightsConfig)
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
    # Optional overrides for Reddit / community search (else use settings.community.reddit.queries).
    community_queries: list[str] = Field(default_factory=list)
    reddit_subreddits: list[str] = Field(default_factory=list)


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
    settings = load_settings(base / "settings.yaml")
    insights = settings.insights
    if insights.enabled and insights.lenses_file and not insights.lenses:
        lens_data = _read_yaml(base / insights.lenses_file).get("lenses", [])
        settings = settings.model_copy(
            update={"insights": insights.model_copy(update={"lenses": [InsightLens(**l) for l in lens_data]})}
        )
    return Config(
        settings=settings,
        registry=load_products(base / "products.yaml"),
    )

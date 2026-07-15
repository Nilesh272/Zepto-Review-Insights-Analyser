"""Typed data contracts shared between the agent core and its tools.

Mirrors architecture §5. These models flow between pipeline stages; in Phase 0 they are
exercised only by stub tools and round-trip tests, but the shapes are the real ones later
phases build on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["app_store", "play_store"]
RunStatus = Literal["RUNNING", "COMPLETED", "FAILED"]
EmailStatus = Literal["none", "draft", "sent"]


class Span(BaseModel):
    """A redacted region within review text (PII audit)."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    label: str


class RawReview(BaseModel):
    """A review as parsed from a store, before preprocessing."""

    source: Source
    product_id: str
    review_id: str
    rating: int = Field(ge=1, le=5)
    title: str | None = None
    body: str
    author: str | None = None
    locale: str
    posted_at: datetime  # UTC
    app_version: str | None = None


class NormalizedReview(RawReview):
    """A review after merge/dedup/window/quality filtering (Phase 1 output).

    Adds the near-dup fingerprint and the detected language used by the quality filters.
    """

    text_fingerprint: str
    word_count: int = 0
    lang: str | None = None


class CleanReview(RawReview):
    """A review after PII scrubbing and language detection."""

    body_clean: str
    pii_spans: list[Span] = Field(default_factory=list)
    lang: str


class Cluster(BaseModel):
    """A density cluster of semantically similar reviews."""

    cluster_id: int
    review_ids: list[str] = Field(default_factory=list)
    size: int = Field(ge=0)
    score: float
    avg_rating: float


class Quote(BaseModel):
    """A verbatim quote with provenance; only validated quotes may be published."""

    text: str
    review_id: str
    validated: bool = False


class QuoteCandidate(BaseModel):
    """A quote proposed by the summarizer, with the review it claims to come from.

    Candidates are *unverified*: `validate_quotes` is the hard gate that decides which become
    published `Quote`s.
    """

    text: str
    review_id: str


class ThemeDraft(BaseModel):
    """An LLM/summarizer draft for one cluster, before quote grounding (Phase 4)."""

    cluster_id: int
    title: str
    summary: str
    candidate_quotes: list[QuoteCandidate] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    who_this_helps: list[str] = Field(default_factory=list)
    supporting_review_ids: list[str] = Field(default_factory=list)


class Theme(BaseModel):
    """A named theme with grounded quotes, actions, and audience."""

    title: str
    summary: str
    quotes: list[Quote] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    who_this_helps: list[str] = Field(default_factory=list)
    supporting_review_ids: list[str] = Field(default_factory=list)


class RunRecord(BaseModel):
    """Idempotency + audit record for a single (product, iso_week) run (architecture §8.2)."""

    run_id: str
    product_id: str
    iso_week: str  # e.g. "2026-W26"
    status: RunStatus = "RUNNING"
    doc_id: str | None = None
    section_anchor: str | None = None
    heading_id: str | None = None
    deep_link: str | None = None
    email_status: EmailStatus = "none"
    message_id: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    metrics: dict = Field(default_factory=dict)
    error: str | None = None

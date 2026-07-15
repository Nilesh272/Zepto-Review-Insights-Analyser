"""Ingestion layer (architecture §3.2 `fetch_reviews`).

Pulls public reviews from the Apple App Store (iTunes RSS) and Google Play, normalizes,
deduplicates, windows, and applies quality filters into a single `NormalizedReview[]`.
"""

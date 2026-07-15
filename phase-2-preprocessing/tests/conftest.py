"""Shared test fixtures and helpers for Phase 1 ingestion tests."""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def appstore_page1():
    return load_fixture("appstore_page1.json")


@pytest.fixture
def appstore_empty():
    return load_fixture("appstore_empty.json")


@pytest.fixture
def play_entries():
    return load_fixture("play_reviews.json")


@pytest.fixture
def fake_detector():
    """Deterministic stand-in for langdetect: French if it looks French, else English."""

    def detect(text: str):
        t = text.lower()
        if "cette application" in t or "vraiment excellente" in t:
            return "fr"
        return "en"

    return detect


@pytest.fixture
def no_sleep():
    return lambda _seconds: None

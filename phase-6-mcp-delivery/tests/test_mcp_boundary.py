"""E6.10 / X6.11 — no Google SDK is imported anywhere in the agent (MCP-only boundary)."""

from pathlib import Path

import pulse

# Google client/OAuth SDKs that must never appear in the agent codebase (OAuth lives in the
# MCP servers). Note: `google_play_scraper` (ingestion) is NOT a Google SDK and is allowed.
FORBIDDEN = ("googleapiclient", "google.oauth2", "google.auth", "oauth2client", "from google ")


def test_no_google_sdk_imports_in_agent():
    root = Path(pulse.__file__).resolve().parent
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN:
            if needle in text:
                offenders.append((str(path.relative_to(root)), needle))
    assert offenders == [], f"Google SDK imports found outside MCP servers: {offenders}"

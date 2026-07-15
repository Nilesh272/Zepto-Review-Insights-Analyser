"""Tests for Reddit parse + community file-drop ingestion."""

from datetime import datetime, timezone
from pathlib import Path

from pulse.ingestion.community import fetch_community_file_drops, load_community_drop_file
from pulse.ingestion.reddit import parse_reddit_listing, _proxy_rating


def test_proxy_rating_from_upvote_ratio():
    assert _proxy_rating(score=1, upvote_ratio=0.9) == 5
    assert _proxy_rating(score=1, upvote_ratio=0.2) == 1
    assert _proxy_rating(score=100, upvote_ratio=None) == 5


def test_parse_reddit_listing():
    payload = {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "abc123",
                        "title": "Zepto delivery experience in Bangalore",
                        "selftext": "Ordered groceries late night, ETA slipped but support helped eventually.",
                        "created_utc": 1720000000,
                        "subreddit": "bangalore",
                        "author": "user1",
                        "score": 42,
                        "upvote_ratio": 0.8,
                        "stickied": False,
                    },
                },
                {
                    "kind": "t3",
                    "data": {
                        "id": "skip",
                        "title": "short",
                        "selftext": "",
                        "created_utc": 1720000000,
                        "subreddit": "india",
                        "score": 1,
                    },
                },
            ]
        }
    }
    reviews = parse_reddit_listing(payload, "zepto")
    assert len(reviews) == 1
    assert reviews[0].source == "reddit"
    assert reviews[0].review_id.startswith("reddit:bangalore:")
    assert reviews[0].rating == 4
    assert "ETA slipped" in reviews[0].body


def test_community_file_drops(tmp_path: Path):
    product_dir = tmp_path / "zepto"
    product_dir.mkdir()
    (product_dir / "threads.json").write_text(
        """[
          {
            "source": "forum",
            "review_id": "f1",
            "body": "Forum thread about Zepto category discovery and search barriers daily",
            "posted_at": "2026-07-01T00:00:00+00:00",
            "rating": 2
          },
          {
            "source": "social",
            "review_id": "s1",
            "body": "Social post praising Zepto quick commerce late night pharmacy stock",
            "posted_at": "2026-07-02T00:00:00+00:00",
            "rating": 5
          }
        ]
        """,
        encoding="utf-8",
    )
    reviews = fetch_community_file_drops("zepto", drop_dir=tmp_path)
    assert len(reviews) == 2
    sources = {r.source for r in reviews}
    assert sources == {"forum", "social"}


def test_load_jsonl_drop(tmp_path: Path):
    path = tmp_path / "product_review_notes.jsonl"
    path.write_text(
        '{"source":"product_review","review_id":"pr1","body":"Long product review of Zepto search and deals discovery experience","posted_at":"2026-07-03T12:00:00+00:00","rating":4}\n',
        encoding="utf-8",
    )
    reviews = load_community_drop_file(path, "zepto")
    assert len(reviews) == 1
    assert reviews[0].source == "product_review"
    assert reviews[0].posted_at.tzinfo is not None

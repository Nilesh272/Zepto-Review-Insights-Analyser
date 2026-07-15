"""X4.8 — JSON parsing/repair for the generative backend (no network)."""

import pytest

from pulse.models import Cluster
from pulse.reasoning.llm import parse_theme_json


def _cluster():
    return Cluster(cluster_id=2, review_ids=["r1", "r2"], size=2, score=2.0, avg_rating=1.5)


def test_parses_plain_json():
    text = '{"title": "Crashes", "summary": "app crashes", "quotes": [{"text": "it crashes", "review_id": "r1"}], "actions": ["fix crashes"], "who_this_helps": ["Product"]}'
    draft = parse_theme_json(text, _cluster())
    assert draft.title == "Crashes"
    assert draft.cluster_id == 2  # taken from the cluster, not the model
    assert draft.candidate_quotes[0].review_id == "r1"
    assert draft.supporting_review_ids == ["r1", "r2"]


def test_parses_fenced_json_with_prose():
    text = "Sure! Here is the result:\n```json\n{\"title\": \"Support\", \"summary\": \"slow\", \"quotes\": []}\n```\nHope this helps."
    draft = parse_theme_json(text, _cluster())
    assert draft.title == "Support" and draft.candidate_quotes == []


def test_malformed_raises():
    with pytest.raises(ValueError):
        parse_theme_json("not json at all", _cluster())

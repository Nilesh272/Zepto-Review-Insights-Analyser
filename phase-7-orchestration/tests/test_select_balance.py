"""Balanced cluster selection — critical (low-rating) themes are not drowned out by positive ones."""

from pulse.models import Cluster
from pulse.reasoning.select import select_balanced_clusters


def _c(cid, size, avg_rating, rid):
    return Cluster(cluster_id=cid, review_ids=[rid], size=size, score=float(size), avg_rating=avg_rating)


def test_reserves_critical_cluster():
    clusters = [
        _c(0, 50, 4.8, "p1"),   # large positive — rank 1
        _c(1, 40, 4.5, "p2"),
        _c(2, 8, 1.8, "n1"),    # small critical — would be dropped without balancing
        _c(3, 6, 4.2, "p3"),
    ]
    out = select_balanced_clusters(clusters, top_n=3, min_critical=1, critical_max_rating=2.5)
    assert len(out) == 3
    assert any(c.avg_rating <= 2.5 for c in out)
    assert out[0].review_ids == ["n1"]  # critical slot filled first


def test_fills_remaining_by_rank():
    clusters = [
        _c(0, 50, 4.8, "p1"),
        _c(1, 8, 1.5, "n1"),
        _c(2, 30, 4.0, "p2"),
    ]
    out = select_balanced_clusters(clusters, top_n=2, min_critical=1)
    ids = [c.review_ids[0] for c in out]
    assert ids == ["n1", "p1"]


def test_no_critical_when_none_present():
    clusters = [_c(0, 10, 4.5, "a"), _c(1, 8, 4.0, "b")]
    out = select_balanced_clusters(clusters, top_n=2, min_critical=1)
    assert len(out) == 2
    assert all(c.avg_rating > 2.5 for c in out)

from app.rag.metrics import hit_rate_at_k, mrr, ndcg_at_k, precision_at_k, recall_at_k


def test_ranking_metrics_with_labels():
    retrieved = ["d1", "d2", "d3"]
    relevant = {"d2", "d9"}
    assert precision_at_k(retrieved, relevant, 3) == 1 / 3
    assert recall_at_k(retrieved, relevant, 3) == 0.5
    assert hit_rate_at_k(retrieved, relevant, 3) == 1.0
    assert mrr(retrieved, relevant) == 0.5
    assert ndcg_at_k(retrieved, relevant, 3) > 0


def test_metrics_are_zero_without_hits():
    assert precision_at_k(["a"], {"z"}, 1) == 0.0
    assert recall_at_k(["a"], {"z"}, 1) == 0.0
    assert mrr(["a"], {"z"}) == 0.0
    assert hit_rate_at_k(["a"], {"z"}, 1) == 0.0

from promo_engine.config import load_config
from promo_engine.rank.diversity import promo_iou
from promo_engine.rank.learner import evaluate, fit_logistic, to_weights


def test_all_promos_meet_the_brief(sample_run):
    lo, hi = 20, 60
    assert sample_run.promos, "no promos"
    for p in sample_run.promos:
        assert lo - 0.5 <= p.duration <= hi + 0.5, p.id
        assert p.hook["at"] <= 3.0, p.id
        for s in p.segments:   # cut points sit on real beats
            ep = sample_run.show.episode(s.episode)
            assert s.start == ep.beats[s.first_beat].start and s.end == ep.span_end(s.first_beat, s.last_beat)
        assert p.why and p.hook["text"] and p.cliffhanger["text"]


def test_ranks_and_post_order_are_permutations(sample_run):
    n = len(sample_run.promos)
    assert sorted(p.rank for p in sample_run.promos) == list(range(1, n + 1))
    assert sorted(p.post_order for p in sample_run.promos) == list(range(1, n + 1))
    scores = [p.score for p in sorted(sample_run.promos, key=lambda p: p.rank)]
    assert scores == sorted(scores, reverse=True)


def test_no_heavy_overlap_and_episode_cap(sample_run):
    ps = sample_run.promos
    for i, a in enumerate(ps):
        for b in ps[i + 1:]:
            assert promo_iou(a, b) <= 0.35 + 1e-6
    from collections import Counter
    assert max(Counter(p.segments[-1].episode for p in ps).values()) <= 3
    assert sum(len(p.segments) > 1 for p in ps) <= 3


def test_top_promos_are_strong(sample_run):
    top = sorted(sample_run.promos, key=lambda p: p.rank)[:5]
    assert all(p.score >= 70 for p in top)
    assert sum(p.hook["score"] >= 0.6 for p in top) >= 4


def test_platform_preset_changes_lengths(sample_dir):
    from promo_engine.pipeline import run_pipeline
    r = run_pipeline(sample_dir / "show", platform="tiktok", use_llm=False)
    assert r.promos and all(p.duration <= 35.5 for p in r.promos)


def test_learner_separates_classes():
    pos = [({"hook": 0.9, "cliffhanger": 0.8, "standalone": 0.9}, 1) for _ in range(20)]
    neg = [({"hook": 0.1, "cliffhanger": 0.2, "standalone": 0.9}, 0) for _ in range(40)]
    w, b = fit_logistic(pos + neg, epochs=300)
    assert evaluate(pos + neg, w, b)["auc"] > 0.95
    weights = to_weights(w, load_config()["weights"])
    assert weights["hook"] > 0 and weights["spoiler_penalty"] >= 0

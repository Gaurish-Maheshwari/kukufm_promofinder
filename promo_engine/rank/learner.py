"""Learn scorer weights from editors: manual promos + accept/reject feedback.

A tiny L2-regularised logistic regression over the same features the scorer
uses (pure Python, no numpy, so it also runs on Vercel). Positive examples are
windows that match a manual promo or that an editor accepted; negatives are the
highest-scoring windows that did NOT match (hard negatives). The learned
coefficients are mapped back to non-negative weights and saved to
config/learned_weights.yaml, which the pipeline picks up automatically.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from .scorer import POSITIVE

FEATURES = POSITIVE + ["spoiler"]


def _sigmoid(z: float) -> float:
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1 / (1 + math.exp(-z))


def fit_logistic(samples: list[tuple[dict, int]], l2: float = 0.05, lr: float = 0.3, epochs: int = 800, seed: int = 7):
    rng = random.Random(seed)
    w = {k: 0.0 for k in FEATURES}
    b = 0.0
    data = list(samples)
    pos = sum(y for _, y in data) or 1
    neg = (len(data) - pos) or 1
    cw = {1: len(data) / (2 * pos), 0: len(data) / (2 * neg)}   # class balance
    for _ in range(epochs):
        rng.shuffle(data)
        gw = {k: 0.0 for k in FEATURES}
        gb = 0.0
        for x, y in data:
            p = _sigmoid(b + sum(w[k] * float(x.get(k, 0.0)) for k in FEATURES))
            e = (p - y) * cw[y]
            for k in FEATURES:
                gw[k] += e * float(x.get(k, 0.0))
            gb += e
        n = len(data)
        for k in FEATURES:
            w[k] -= lr * (gw[k] / n + l2 * w[k])
        b -= lr * gb / n
    return w, b


def evaluate(samples, w, b) -> dict:
    scored = sorted(((b + sum(w[k] * float(x.get(k, 0.0)) for k in FEATURES), y) for x, y in samples), key=lambda t: -t[0])
    pos = sum(y for _, y in scored)
    neg = len(scored) - pos
    if not pos or not neg:
        return {"auc": None, "n": len(scored), "positives": pos}
    # AUC via rank statistic
    rank_sum, r = 0.0, 0
    for i, (_, y) in enumerate(reversed(scored), 1):
        if y:
            rank_sum += i
    auc = (rank_sum - pos * (pos + 1) / 2) / (pos * neg)
    return {"auc": round(auc, 3), "n": len(scored), "positives": pos}


def to_weights(w: dict, base_weights: dict) -> dict:
    """Map coefficients to non-negative scorer weights with the same total as the base."""
    total = sum(float(base_weights.get(k, 0)) for k in POSITIVE) or 1.0
    raw = {k: max(0.01, w[k]) for k in POSITIVE}
    s = sum(raw.values())
    out = {k: round(total * v / s, 4) for k, v in raw.items()}
    out["spoiler_penalty"] = round(max(0.0, -w.get("spoiler", 0.0)) * total / s, 4) if s else 0.0
    # blend 50/50 with the hand-set weights: a few dozen labels should not erase priors
    return {k: round(0.5 * out.get(k, 0) + 0.5 * float(base_weights.get(k, 0)), 4) for k in list(POSITIVE) + ["spoiler_penalty"]}


def build_samples(pool: Iterable, positives_features: list[dict], is_positive, neg_ratio: int = 5, seed: int = 7):
    pool = list(pool)
    pos = [(c.features, 1) for c in pool if is_positive(c)] + [(f, 1) for f in positives_features]
    negs = [c for c in sorted(pool, key=lambda c: -c.score) if not is_positive(c)]
    k = min(len(negs), max(10, neg_ratio * max(1, len(pos))))
    hard = negs[: k // 2]
    rng = random.Random(seed)
    rest = negs[k // 2:]
    soft = rng.sample(rest, min(len(rest), k - len(hard)))
    return pos + [(c.features, 0) for c in hard + soft]


def save_learned(weights: dict, path: Path, stats: dict) -> None:
    path.write_text(yaml.safe_dump({
        "learned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "training": stats,
        "weights": weights,
    }, sort_keys=False), encoding="utf-8")

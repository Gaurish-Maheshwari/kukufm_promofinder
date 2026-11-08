"""Runs only when the confidential input pack is present in data/input/ (skipped in CI / public clones)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "input"
HAS_PACK = any(p.is_file() and p.suffix.lower() in (".txt", ".pdf", ".docx", ".zip") and p.name.lower() != "readme.md"
               for p in INPUT.rglob("*")) if INPUT.exists() else False
pytestmark = pytest.mark.skipif(not HAS_PACK, reason="input pack not in data/input")


@pytest.fixture(scope="module")
def real_run():
    from promo_engine.pipeline import run_pipeline
    return run_pipeline(INPUT, use_llm=False)


def test_every_episode_parsed_and_timed(real_run):
    eps = real_run.show.episodes
    assert len(eps) >= 10
    assert [e.number for e in eps] == list(range(1, len(eps) + 1))       # no gaps, no duplicates
    for e in eps:
        assert e.parse_confidence >= 0.95, e.number
        assert not any(b.speaker in ("START", "END", "EPISODE NUMBER") for b in e.beats)


def test_promos_meet_the_brief_on_real_pack(real_run):
    assert len(real_run.promos) >= 10
    lo, hi = real_run.cfg["promo"]["min_seconds"], real_run.cfg["promo"]["max_seconds"]
    for p in real_run.promos:
        assert lo - 0.5 <= p.duration <= hi + 0.5
        assert p.hook["at"] <= 3.0
        for s in p.segments:
            ep = real_run.show.episode(s.episode)
            assert s.end == ep.span_end(s.first_beat, s.last_beat)
    assert real_run.metrics["diversity"]["episodes_in_top10"] >= 6
    assert not real_run.metrics["degraded_stages"]


def test_title_and_metadata(real_run):
    assert real_run.show.title and real_run.show.title != "Untitled show"
    assert any(e.meta for e in real_run.show.episodes)

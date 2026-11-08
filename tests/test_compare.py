from promo_engine.evaluate.compare import compare, overlap_stats
from promo_engine.evaluate.manual import ManualPromo, load_manual
from promo_engine.models import Promo, Segment


def _p(pid, *segs, rank=1):
    p = Promo(id=pid, segments=[Segment(e, s, t, 0, 0) for e, s, t in segs])
    p.rank = rank
    p.hook = {"timestamp": segs[0][1], "episode": segs[0][0]}
    return p


def test_iou_math():
    m = ManualPromo("M", [(1, 10, 40)])
    assert overlap_stats(m, _p("A", (1, 10, 40)))["iou"] == 1.0
    assert overlap_stats(m, _p("B", (2, 10, 40)))["iou"] == 0.0           # other episode
    st = overlap_stats(m, _p("C", (1, 25, 55)))
    assert abs(st["iou"] - 15 / 45) < 1e-9 and abs(st["coverage"] - 0.5) < 1e-9


def test_compare_counts_and_one_to_one():
    cfg = {"promo": {"min_seconds": 20, "max_seconds": 60}, "evaluation": {"match_iou": 0.3, "match_coverage": 0.5}}
    manual = [ManualPromo("M1", [(1, 10, 40)]), ManualPromo("M2", [(1, 12, 42)]), ManualPromo("M3", [(5, 0, 30)]),
              ManualPromo("M4", [(2, 0, 90)])]
    ai = [_p("P1", (1, 10, 40), rank=1), _p("P2", (5, 50, 80), rank=2)]
    res = compare(ai, manual, None, cfg)
    s = res["summary"]
    assert s["manual_total"] == 4 and s["matched"] == 1          # P1 can match only one of M1/M2
    statuses = {r["manual"]["id"]: r["status"] for r in res["rows"]}
    assert statuses["M3"] == "missed"
    assert "outside" in next(r for r in res["rows"] if r["manual"]["id"] == "M4")["diagnosis"]
    assert s["headline"].startswith("The tool found 1 of your 4")


def test_load_manual_csv_multisegment(sample_dir):
    ms = load_manual(sample_dir / "manual_promos_sample.csv")
    assert len(ms) == 10
    m2 = next(m for m in ms if m.id == "M2")
    assert len(m2.segments) == 2 and m2.segments[1] == (1, 72.0, 95.0)


def test_load_manual_free_text(fixtures):
    ms = load_manual(fixtures / "manual_notes.txt")
    assert len(ms) == 2
    assert ms[0].id == "M1" and ms[0].segments == [(1, 0.0, 25.0)] and ms[0].hook == "wine"
    assert ms[1].segments == [(2, 10.0, 30.0), (3, 0.0, 12.0)]


def test_load_manual_json():
    data = b'[{"id": "X", "segments": [{"episode": 4, "start": "01:06", "end": "01:43"}], "hook": "slap"}]'
    ms = load_manual(("m.json", data))
    assert ms[0].segments == [(4, 66.0, 103.0)]


def test_sample_recall(sample_run):
    s = sample_run.comparison["summary"]
    assert s["manual_total"] == 10
    assert s["recall"] >= 0.8
    row = next(r for r in sample_run.comparison["rows"] if r["manual"]["id"] == "M6")   # the gala slap
    assert row["status"] == "matched"

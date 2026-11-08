from promo_engine.analysis.characters import build_registry
from promo_engine.analysis.features import annotate_show
from promo_engine.analysis.lexicon import Lexicon
from promo_engine.analysis.standalone import standalone_score
from promo_engine.models import SourceDoc
from promo_engine.ingest import parse_show


def _show(text):
    show = parse_show([SourceDoc("e.txt", "e.txt", text, "txt", 1)])
    build_registry(show)
    annotate_show(show)
    return show


def test_hook_cues():
    s = _show("[00:00] ACTION: Chloe slaps Ava across the face.\n[00:03] AVA: Good morning.\n[00:05] VIVIAN: How dare you!\n")
    b = s.episodes[0].beats
    assert b[0].signals["hook"] > 0.9 and b[0].signals["hook_type"] == "physical"
    assert b[1].signals["hook"] < 0.3
    assert b[2].signals["hook"] > 0.7


def test_cliffhanger_and_resolution():
    s = _show("[00:00] AVA: Who are you?\n[00:03] ETHAN: I'm the—\n[00:05] AVA: Okay. Thank you.\n[00:07] ACTION: The door bursts open.\n")
    b = s.episodes[0].beats
    assert b[0].signals["cliff_type"] in ("open_question", "reveal_pending") and b[0].signals["cliff"] > 0.7
    assert b[1].signals["cliff_type"] == "interrupted"
    assert b[2].signals["resolution"] > 0.5
    assert b[3].signals["cliff"] > 0.7


def test_false_positive_guards():
    """'maid' as a description or 'knees' in an apology must not count as a shocking line."""
    s = _show("[00:00] ACTION: Ava, in a maid's uniform, carries a tray.\n[00:03] VIVIAN: I owe you an apology for the knees.\n")
    b = s.episodes[0].beats
    assert b[0].signals["hook"] < 0.5
    assert b[1].signals.get("hook_type") != "shocking_line"


def test_tropes():
    lex = Lexicon()
    assert "pregnancy_baby" in lex.tropes_in("You're eight weeks pregnant.")
    assert "slap_humiliation" in lex.tropes_in("She slaps her in front of everyone.")


def test_standalone_penalties():
    s = _show("[00:00] AVA: Did you lie?\n[00:03] ETHAN: Yes, like I said last night.\n[00:06] AVA: Then go.\n")
    ep = s.episodes[0]
    good, _ = standalone_score(ep, 0, 2)
    bad, reasons = standalone_score(ep, 1, 2)
    assert bad < good
    assert any("mid-conversation" in r or "earlier" in r for r in reasons)


def test_character_registry():
    s = _show("[00:00] AVA: Hi.\n[00:02] ETHAN STERLING: Hello, Ava.\n[00:04] AVA: Sterling.\n")
    assert set(s.characters) == {"AVA", "ETHAN STERLING"}
    assert "ETHAN STERLING" in s.episodes[0].beats[2].signals["mentions"]

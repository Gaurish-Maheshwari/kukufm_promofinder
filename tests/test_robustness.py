"""Messy inputs and single points of failure: the run must degrade, never die."""
import io
import zipfile

import pytest

from promo_engine.config import load_config
from promo_engine.ingest import load_inputs, parse_show
from promo_engine.pipeline import run_pipeline

BLOCK = """EPISODE NUMBER: Episode 3
EPISODE LOGLINE: test
--- SCRIPT START ---
SCENE 01
Scene heading: INT. HALL – NIGHT
Scene start: 00:00.00
**ACTION:**
Start: (00:00.00) | End: (00:05.00)
She slaps him hard across the face.
**AVA (Furious):**
Start: (00:05.20) | End: (00:09.00)
"How dare you lie to me!"
**BEN (Cold):**
Start: (00:09.20) | End: (00:14.00)
"You were never my wife. You were a contract."
**ACTION:**
Start: (00:14.00) | End: (00:19.00)
The doors burst open. Guards storm in with drawn swords.
**AVA (Terrified):**
Start: (00:19.20) | End: (00:24.00)
"Who sent you?"
"""


def _variants() -> dict[str, str]:
    v = {
        "original": BLOCK,
        "crlf": BLOCK.replace("\n", "\r\n"),
        "no_markdown": BLOCK.replace("**", ""),
        "lowercase_labels": BLOCK.replace("**ACTION:**", "**Action:**"),
        "extra_blank_lines": BLOCK.replace("\n", "\n\n"),
        "no_blank_lines": "\n".join(l for l in BLOCK.splitlines() if l.strip()),
        "bullets": "\n".join(("- " + l) if l.startswith("**") else l for l in BLOCK.splitlines()),
        "inline_timing": BLOCK.replace("**\nStart:", "** Start:"),
        "start_end_no_pipe": BLOCK.replace(" | End: ", " End: "),
        "hh_mm_ss_times": BLOCK.replace("(00:", "(00:00:"),
        "nbsp_and_tabs": BLOCK.replace(" ", " ", 20).replace("Start:", "\tStart:"),
        "utf16": BLOCK,
    }
    return v


@pytest.mark.parametrize("name", list(_variants()))
def test_layout_variants_parse_the_same(name, tmp_path):
    text = _variants()[name]
    data = text.encode("utf-16") if name == "utf16" else text.encode("utf-8")
    show = parse_show(load_inputs([("ep.txt", data)]))
    assert len(show.episodes) == 1, name
    ep = show.episodes[0]
    content = [b for b in ep.beats if b.kind != "scene"]
    assert len(content) == 5, (name, [(b.kind, b.text[:30]) for b in content])
    assert sum(b.timed for b in content) >= 5, name
    assert {b.speaker for b in content if b.speaker} == {"AVA", "BEN"}, name
    assert ep.number == 3


def test_wrong_and_missing_extensions(tmp_path):
    (tmp_path / "episode_one").write_text(BLOCK)                         # no extension
    (tmp_path / "ep2.script.bak").write_text(BLOCK.replace("Episode 3", "Episode 4"))   # unknown extension
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ep5.txt", BLOCK.replace("Episode 3", "Episode 5"))
    (tmp_path / "archive.dat").write_bytes(buf.getvalue())              # a zip without .zip
    (tmp_path / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    (tmp_path / "empty.txt").write_text("")
    warnings = []
    show = parse_show(load_inputs(tmp_path, warnings))
    assert sorted(e.number for e in show.episodes) == [3, 4, 5]
    assert any("photo.png" in w for w in warnings)


def test_html_and_odt_inputs(tmp_path):
    html = "<html><body>" + "".join(f"<p>{l}</p>" for l in BLOCK.splitlines()) + "</body></html>"
    (tmp_path / "ep.html").write_text(html)
    show = parse_show(load_inputs(tmp_path))
    assert len([b for b in show.episodes[0].beats if b.kind != "scene"]) == 5
    odt = io.BytesIO()
    with zipfile.ZipFile(odt, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        z.writestr("content.xml", "<office:document>" + "".join(f"<text:p>{l.replace('&', '&amp;').replace('<', '&lt;')}</text:p>" for l in BLOCK.splitlines()) + "</office:document>")
    show2 = parse_show(load_inputs([("ep.odt", odt.getvalue())]))
    assert len([b for b in show2.episodes[0].beats if b.kind != "scene"]) == 5


def test_no_timestamps_at_all_still_runs():
    text = "EPISODE 1\nAVA: You slapped me!\nBEN: And I would do it again.\n" * 20
    r = run_pipeline([("ep1.txt", text.encode())], use_llm=False, overrides={"promo": {"min_score": 0}})
    assert r.promos
    assert all("interpolated_timing" in p.flags for p in r.promos)


def test_garbage_input_gives_clear_error():
    with pytest.raises(ValueError):
        run_pipeline([("x.bin", bytes(range(256)) * 10)], use_llm=False)


def test_structure_agnostic_fallback_reader():
    # an odd house style the main reader does not know: time in the middle of the line
    lines = [f"Line {i} — at 00:{i * 3:02d}.00 — AVA says something shocking: you are fired #{i}!" for i in range(1, 15)]
    show = parse_show(load_inputs([("ep1.txt", "\n".join(lines).encode())]))
    ep = show.episodes[0]
    content = [b for b in ep.beats if b.kind != "scene"]
    assert sum(b.timed for b in content) / len(content) > 0.9


def test_min_score_relaxation_flags_instead_of_returning_nothing(sample_dir):
    r = run_pipeline(sample_dir / "show", use_llm=False, overrides={"promo": {"min_score": 99.9}})
    assert r.promos and all("below_min_score" in p.flags for p in r.promos)
    assert any("minimum score" in w for w in r.warnings)


def test_failing_stage_degrades_not_dies(sample_dir, monkeypatch):
    import promo_engine.pipeline as pl

    def boom(*a, **k):
        raise RuntimeError("simulated montage bug")
    monkeypatch.setattr(pl, "generate_montages", boom)
    r = run_pipeline(sample_dir / "show", use_llm=False)
    assert r.promos
    assert "montages" in r.metrics["degraded_stages"]


def test_export_failure_is_isolated(sample_run, tmp_path, monkeypatch):
    import promo_engine.export.report_html as rh
    from promo_engine.export import exporters

    monkeypatch.setattr(rh, "html_report", lambda run: (_ for _ in ()).throw(RuntimeError("bad html")))
    files = exporters.save_outputs(sample_run.to_dict(), tmp_path, sample_run.cfg)
    assert "promos.json" in files and "editor_cut_sheet.csv" in files
    assert "EXPORT_ERRORS.txt" in files and "bad html" in (tmp_path / "EXPORT_ERRORS.txt").read_text()


def test_corrupt_config_falls_back_to_builtin(tmp_path, monkeypatch):
    import promo_engine.config as c
    bad = tmp_path / "default.yaml"
    bad.write_text("promo: [this is: not: valid")
    monkeypatch.setattr(c, "DEFAULT_CONFIG", bad)
    cfg = c.load_config()
    assert cfg["promo"]["min_seconds"] == 20 and cfg["weights"]["hook"] > 0
    lex_file = tmp_path / "lex.yaml"
    lex_file.write_text("hook: {}\n")
    assert c.load_lexicons(lex_file)["hook"]          # incomplete lexicon -> built-in copy


def test_bad_regex_in_lexicon_is_skipped():
    from promo_engine.analysis.lexicon import BAD_PATTERNS, Lexicon
    from promo_engine.config import load_lexicons
    data = load_lexicons()
    data["hook"]["physical"]["patterns"].append("([unclosed")
    lex = Lexicon(data)
    assert lex.hook and any("unclosed" in b for b in BAD_PATTERNS)


def test_builtin_defaults_match_yaml():
    """promo_engine/defaults.py must mirror config/*.yaml (run scripts/sync_defaults.py after edits)."""
    import yaml
    from promo_engine.config import CONFIG_DIR
    from promo_engine.defaults import DEFAULT_CONFIG, DEFAULT_LEXICONS
    assert yaml.safe_load((CONFIG_DIR / "default.yaml").read_text()) == DEFAULT_CONFIG
    assert yaml.safe_load((CONFIG_DIR / "lexicons.yaml").read_text()) == DEFAULT_LEXICONS


def test_llm_fallback_chain_switches_provider(sample_dir, monkeypatch, tmp_path):
    from promo_engine.llm import providers
    calls = {"gsk": 0}
    real_call = providers.LLMClient._call_with_retry

    def flaky(self, system, user):
        if self.settings.provider == "groq":
            calls["gsk"] += 1
            raise providers.LLMError("401 invalid key")
        return real_call(self, system, user)
    monkeypatch.setattr(providers.LLMClient, "_call_with_retry", flaky)
    monkeypatch.setattr(providers.LLMClient, "_discover_model", lambda self: self.spec.default_model)
    monkeypatch.setenv("LLM_FALLBACK_API_KEYS", "mock")
    cfg = load_config(overrides={"llm": {"cache_dir": str(tmp_path / "c"), "rerank_top_n": 10}})
    r = run_pipeline(sample_dir / "show", cfg=cfg, llm_key="gsk_primarykey123")
    assert r.llm["judged"] == 10
    assert r.llm.get("provider_switches")
    assert calls["gsk"] <= 2                        # circuit breaker: the dead provider is not hammered


def test_circuit_breaker_and_budget(sample_dir, monkeypatch, tmp_path):
    from promo_engine.llm import providers
    n = {"calls": 0}

    def dead(self, system, user):
        n["calls"] += 1
        raise providers.LLMError("503 down")
    monkeypatch.setattr(providers.LLMClient, "_call_with_retry", dead)
    cfg = load_config(overrides={"llm": {"cache_dir": str(tmp_path / "c"), "rerank_top_n": 30, "max_concurrency": 1}})
    r = run_pipeline(sample_dir / "show", cfg=cfg, llm_key="mock")
    assert r.promos and all(p.source == "rules" for p in r.promos)
    assert r.llm["circuit_breaker_open"] and r.llm["skipped_batches"] >= 1
    assert n["calls"] <= 3

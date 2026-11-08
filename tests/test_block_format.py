"""The Kuku input-pack layout: metadata header, SCENE blocks, and **LABEL (manner):** /
Start: (mm:ss.ff) | End: (mm:ss.ff) / text blocks with overlapping camera shots.
Fixtures are synthetic (written for the tests) in the same layout as the real pack."""
from promo_engine.ingest import load_inputs, parse_show
from promo_engine.pipeline import run_pipeline


def _show(fixtures):
    return parse_show(load_inputs(fixtures / "block_format"))


def test_every_block_becomes_a_timed_beat(fixtures):
    show = _show(fixtures)
    assert [e.number for e in show.episodes] == [1, 2]
    ep1 = show.episodes[0]
    content = [b for b in ep1.beats if b.kind != "scene"]
    blocks = (fixtures / "block_format" / "episode-001-Episode 9990001.txt").read_text().count("Start: (")
    assert len(content) == blocks
    assert all(b.timed for b in content)
    assert ep1.parse_confidence == 1.0


def test_kinds_speakers_manners(fixtures):
    ep1 = _show(fixtures).episodes[0]
    kinds = {b.kind for b in ep1.beats}
    assert {"scene", "camera", "action", "dialogue", "sfx"} <= kinds
    stranger = [b for b in ep1.beats if b.speaker == "THE MASKED STRANGER"]
    assert len(stranger) == 2                                   # "THE …" is a name, not a stop-word
    assert stranger[0].manner == "off-screen, Calm, Commanding"  # two parentheticals
    assert any(b.speaker == "LADY MARA" for b in ep1.beats)


def test_metadata_is_not_dialogue(fixtures):
    ep1 = _show(fixtures).episodes[0]
    assert "masquerade" in ep1.meta["episode_logline"]
    assert "continuity_notes" in ep1.meta
    assert not any("LOGLINE" in (b.speaker or "") or "SCRIPT" in b.text for b in ep1.beats)
    assert not any(b.speaker in ("START", "END", "EPISODE NUMBER") for b in ep1.beats)


def test_scene_fields_upper_and_lower_case(fixtures):
    show = _show(fixtures)
    assert show.episodes[0].scenes[0].heading == "INT. GRAND BALLROOM – NIGHT"
    assert show.episodes[1].scenes[0].heading == "INT. GRAND BALLROOM – CONTINUOUS"


def test_overlapping_beats_sorted_and_spans_use_latest_end(fixtures):
    ep2 = _show(fixtures).episodes[1]
    starts = [b.start for b in ep2.beats]
    assert starts == sorted(starts)
    # countess line 0.0–2.5 overlaps the whip-pan shot 0.0–3.0
    i = next(b.idx for b in ep2.beats if b.speaker == "COUNTESS VALE")
    j = next(b.idx for b in ep2.beats if b.kind == "camera")
    assert ep2.span_end(min(i, j), max(i, j)) == 3.0


def test_episode_number_from_header_beats_file_name(fixtures, tmp_path):
    txt = (fixtures / "block_format" / "episode-002-Episode 9990002.txt").read_text()
    (tmp_path / "episode-007-whatever.txt").write_text(txt)
    show = parse_show(load_inputs(tmp_path))
    assert show.episodes[0].number == 2


def test_aliases_merge_honorifics(fixtures):
    r = run_pipeline(fixtures / "block_format", use_llm=False, overrides={"promo": {"min_score": 0}})
    assert "MARA" in r.show.characters
    assert "LADY MARA" in r.show.characters["MARA"]["also_credited_as"]


def test_promos_on_block_format(fixtures):
    r = run_pipeline(fixtures / "block_format", use_llm=False, overrides={"promo": {"min_score": 0}})
    assert r.promos
    for p in r.promos:
        ep = r.show.episode(p.segments[0].episode)
        s = p.segments[0]
        assert s.end == ep.span_end(s.first_beat, s.last_beat)
        # never cut while another beat is still playing
        nxt = s.last_beat + 1
        if nxt < len(ep.beats):
            assert ep.beats[nxt].start >= s.end - 0.05
    hooks = " ".join(p.hook["text"] for p in r.promos)
    assert "Seize her" in hooks or "grab" in hooks or "shot rings out" in hooks.lower()

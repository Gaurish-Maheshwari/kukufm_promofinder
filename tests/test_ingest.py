import io
import zipfile

from promo_engine.ingest import episode_from_name, load_inputs, natural_key, parse_show


def test_episode_from_name():
    assert episode_from_name("Episode 12.txt") == 12
    assert episode_from_name("ep_03_final.pdf") == 3
    assert episode_from_name("S01E07.docx") == 7
    assert episode_from_name("07.txt") == 7
    assert episode_from_name("Episode Five.txt") == 5
    assert episode_from_name("notes.txt") is None


def test_natural_sort():
    assert sorted(["Ep 10", "Ep 2", "Ep 1"], key=natural_key) == ["Ep 1", "Ep 2", "Ep 10"]


def test_load_folder_and_skip_junk(tmp_path, fixtures):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "Ep 2.txt").write_text((fixtures / "classic.txt").read_text())
    (tmp_path / ".DS_Store").write_bytes(b"x")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    warnings = []
    docs = load_inputs(tmp_path, warnings)
    assert [d.name for d in docs] == ["Ep 2.txt"]
    assert docs[0].episode_hint == 2
    assert any("unsupported" in w for w in warnings)


def test_nested_zip_and_bytes(fixtures):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("Ep 3.txt", (fixtures / "classic.txt").read_text())
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("show/Ep 1.txt", "[00:00] AVA: Hello.\n[00:05] ETHAN: Hi.")
        z.writestr("show/more.zip", inner.getvalue())
        z.writestr("__MACOSX/show/._Ep 1.txt", "junk")
    docs = load_inputs([("upload.zip", outer.getvalue())])
    assert sorted(d.episode_hint for d in docs) == [1, 3]


def test_bracketed_multi_episode(fixtures):
    show = parse_show(load_inputs(fixtures / "bracketed.txt"))
    assert [e.number for e in show.episodes] == [1, 2]
    ep1 = show.episodes[0]
    assert ep1.title == "Pilot"
    kinds = [b.kind for b in ep1.beats]
    assert kinds[:3] == ["scene", "action", "dialogue"]
    ava = next(b for b in ep1.beats if b.speaker == "AVA")
    assert ava.manner == "quietly" and ava.start == 6 and ava.end == 9
    assert any(b.kind == "sfx" for b in ep1.beats)
    assert ep1.parse_confidence == 1.0


def test_pipe_table(fixtures):
    ep = parse_show(load_inputs(fixtures / "pipe_table.txt")).episodes[0]
    assert ep.number == 3
    assert [b.kind for b in ep.beats] == ["scene", "action", "dialogue", "dialogue"]   # header row skipped
    m = ep.beats[2]
    assert m.speaker == "MARCUS" and m.manner == "whispering" and (m.start, m.end) == (4, 7)


def test_classic_layout(fixtures):
    ep = parse_show(load_inputs(fixtures / "classic.txt")).episodes[0]
    dl = [b for b in ep.beats if b.kind == "dialogue"]
    assert [(b.speaker, b.start) for b in dl] == [("AVA", 2), ("MARCUS", 8)]
    assert dl[0].manner == "whispering"
    assert any(b.kind == "action" and "envelope" in b.text for b in ep.beats)


def test_interpolation(fixtures):
    ep = parse_show(load_inputs(fixtures / "untimed_lines.txt")).episodes[0]
    starts = [b.start for b in ep.beats]
    assert starts == sorted(starts) and starts[0] == 0 and starts[-1] == 20
    assert [b.timed for b in ep.beats] == [True, False, False, True]
    assert 0 < ep.beats[1].start < ep.beats[2].start < 20
    assert ep.parse_confidence == 0.5


def test_absolute_times_shifted(fixtures):
    ep = parse_show(load_inputs(fixtures / "absolute_times.txt")).episodes[0]
    assert ep.beats[0].start == 0 and ep.beats[1].start == 4


def test_split_on_timestamp_reset(fixtures):
    show = parse_show(load_inputs(fixtures / "two_eps_no_headers.txt"))
    assert len(show.episodes) == 2


def test_srt(fixtures):
    ep = parse_show(load_inputs(fixtures / "subs.srt")).episodes[0]
    assert ep.beats[0].speaker == "AVA" and ep.beats[0].end == 3.5
    assert ep.beats[1].speaker == "CHLOE"


def test_sample_formats_all_parse(sample_dir):
    show = parse_show(load_inputs(sample_dir / "sample_show.zip"))
    assert [e.number for e in show.episodes] == list(range(1, 9))
    for e in show.episodes:
        assert e.parse_confidence >= 0.95, e.number
        assert 75 < e.duration < 110
        assert not any("CONFIDENTIAL" in b.text for b in e.beats)   # PDF running header removed

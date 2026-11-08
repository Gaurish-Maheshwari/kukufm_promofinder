import pytest

from promo_engine.timecode import fmt, parse_timecode, smpte, split_leading_timecode


@pytest.mark.parametrize("tok,expected", [
    ("0:12", 12.0), ("00:12", 12.0), ("1:02:03", 3723.0), ("00:01:23,456", 83.456), ("00:01:23.5", 83.5),
    ("00:00:05:15", 5.5), ("1m23s", 83.0), ("83s", 83.0), ("12", 12.0), ("01:05.25", 65.25),
])
def test_parse(tok, expected):
    assert parse_timecode(tok) == pytest.approx(expected)


def test_parse_rejects_garbage():
    assert parse_timecode("hello") is None
    assert parse_timecode("") is None


@pytest.mark.parametrize("line,start,end,rest", [
    ("[00:00:07] CHLOE: Careful.", 7, None, "CHLOE: Careful."),
    ("00:03 - 00:06 | AVA | Hi", 3, 6, "AVA | Hi"),
    ("(0:12) Ava walks in.", 12, None, "Ava walks in."),
    ("[00:00:01,000 --> 00:00:03,500] text", 1, 3.5, "text"),
    ("INT. HALL - NIGHT [00:12 - 00:40]", 12, 40, "INT. HALL - NIGHT"),
    ("12 people stand up.", None, None, "12 people stand up."),
])
def test_split_leading(line, start, end, rest):
    s, e, r = split_leading_timecode(line)
    assert (s, e) == ((None if start is None else pytest.approx(start)), (None if end is None else pytest.approx(end)))
    assert r.startswith(rest.split()[0]) if rest else r == ""


def test_formats():
    assert fmt(83.456) == "01:23.5"
    assert fmt(83.456, "hms") == "00:01:23.456"
    assert fmt(83.4, "srt") == "00:01:23,400"
    assert smpte(5.5) == "00:00:05:15"

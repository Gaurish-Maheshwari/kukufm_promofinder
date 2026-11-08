import pytest

from promo_engine.config import load_config
from promo_engine.llm import LLMCache, build_client, detect_provider, parse_json_loose, resolve_settings
from promo_engine.llm.base import mask


@pytest.mark.parametrize("key,provider", [
    ("AIzaSyA-xxxxxxxxxxxxxxxxxxxxxxxxxxxx", "gemini"), ("AQ.Ab8RN6Kxxxxxxxxxxxxxxxxx3euw", "gemini"), ("gsk_abcdefghijkl", "groq"),
    ("sk-ant-api03-xyz", "anthropic"), ("sk-or-v1-abc", "openrouter"), ("sk-proj-abc123", "openai"),
    ("sk-" + "a" * 48, "openai"), ("sk-" + "0123456789abcdef" * 2, "deepseek"), ("xai-123", "xai"),
    ("nvapi-abc", "nvidia"), ("hf_abc", "huggingface"), ("csk-abc", "cerebras"), ("ollama", "ollama"),
    ("mock", "mock"), ("random-key-without-prefix", None), ("", None),
])
def test_detect_provider(key, provider):
    assert detect_provider(key) == provider


def test_resolve_settings_overrides(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "gsk_123456789")
    s = resolve_settings()
    assert s.provider == "groq" and s.describe()["base_url"].startswith("https://api.groq.com")
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert not resolve_settings().enabled
    monkeypatch.delenv("LLM_PROVIDER")
    monkeypatch.setenv("LLM_API_KEY", "whatever")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8001/v1")
    assert resolve_settings().provider == "custom"


def test_legacy_env_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaTest1234567")
    assert resolve_settings().provider == "gemini"


def test_mask_never_leaks_key():
    assert "SECRET" not in mask("sk-ant-SECRETSECRETSECRET-1234")


def test_parse_json_loose():
    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_loose('Sure! Here it is: {"a": [1, 2,],}') == {"a": [1, 2]}
    assert parse_json_loose("[1,2]") == {"results": [1, 2]}


def test_cache_roundtrip(tmp_path):
    c = LLMCache(tmp_path)
    k = c.key("p", "m", "sys", "user")
    assert c.get(k) is None
    c.set(k, {"x": 1})
    assert c.get(k) == {"x": 1}


def test_no_key_means_rules_only():
    assert build_client(load_config()) is None


def test_mock_llm_rerank_end_to_end(sample_dir, tmp_path):
    from promo_engine.pipeline import run_pipeline
    cfg = load_config(overrides={"llm": {"cache_dir": str(tmp_path / "c"), "rerank_top_n": 10}})
    r = run_pipeline(sample_dir / "show", cfg=cfg, llm_key="mock")
    assert r.llm["judged"] == 10 and r.llm["failed_batches"] == 0
    assert any(p.source == "rules+llm" for p in r.promos)
    # second run is served from cache
    r2 = run_pipeline(sample_dir / "show", cfg=load_config(overrides={"llm": {"cache_dir": str(tmp_path / "c"), "rerank_top_n": 10}}), llm_key="mock")
    assert r2.llm["stats"]["cache_hits"] == 2 and r2.llm["stats"]["calls"] == 0


def test_llm_boundary_edits_are_guarded(sample_run):
    """The model may only move cut points to real lines inside the clip, within length limits."""
    from promo_engine.llm.judge import _apply_edit, _render_candidate
    from promo_engine.generate.candidates import Candidate
    p = next(p for p in sample_run.promos if p.kind == "continuous")
    c = Candidate(segments=list(p.segments), features={})
    _, lm = _render_candidate("c1", c, sample_run.show)
    n = max(lm)
    assert _apply_edit(c, {"start_line": n + 5, "end_line": n + 9}, lm, sample_run.show, sample_run.cfg, sample_run.lexicon).startswith("rejected")
    assert _apply_edit(c, {"start_line": n, "end_line": n}, lm, sample_run.show, sample_run.cfg, sample_run.lexicon).startswith("rejected")


def test_failing_llm_falls_back_to_rules(sample_dir, monkeypatch, tmp_path):
    from promo_engine.llm import providers
    from promo_engine.pipeline import run_pipeline

    def boom(self, system, user):
        raise providers.LLMError("simulated outage")
    monkeypatch.setattr(providers.LLMClient, "_call_with_retry", boom)
    cfg = load_config(overrides={"llm": {"cache_dir": str(tmp_path / "c2")}})
    r = run_pipeline(sample_dir / "show", cfg=cfg, llm_key="mock")
    assert r.promos and r.llm["failed_batches"] > 0
    assert all(p.source == "rules" for p in r.promos)


def test_gemini_auth_route_fallback(monkeypatch):
    """A Google key rejected on the header route is retried with ?key= and the working route is remembered."""
    import httpx
    from promo_engine.llm.base import LLMSettings
    from promo_engine.llm.providers import LLMClient

    calls = []

    def fake_post(self, url, headers=None, params=None, json=None, **kw):
        calls.append(("header" if headers and "x-goog-api-key" in headers else "query", url))
        req = httpx.Request("POST", url)
        if headers and "x-goog-api-key" in headers:
            return httpx.Response(401, request=req, json={"error": {"message": "unauthenticated"}})
        return httpx.Response(200, request=req, json={
            "candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}],
            "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2}})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    s = LLMSettings(key="AQ.Ab8RN6Kxxxxxxxxxxxxxxxxx3euw", provider="gemini", model="gemini-2.5-flash", base_url=None)
    client = LLMClient(s)
    client._model = "gemini-2.5-flash"
    out = client._call("sys", "user")
    assert '"ok"' in out
    assert [c[0] for c in calls] == ["header", "query"]
    assert client.stats["gemini_route"] == "ai-studio query"
    calls.clear()
    client._call("sys", "user")
    assert [c[0] for c in calls] == ["query"]       # remembered


def test_unknown_key_hint_mentions_provider():
    from promo_engine.llm.base import unknown_key_hint
    assert "LLM_PROVIDER=gemini" in unknown_key_hint("zz-weird-key-123456")

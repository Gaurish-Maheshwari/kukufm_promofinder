"""Model-agnostic LLM layer: one API key selects the provider."""
from .base import PROVIDERS, LLMSettings, detect_provider, mask, resolve_settings
from .cache import LLMCache
from .providers import LLMClient, LLMError, parse_json_loose

__all__ = ["PROVIDERS", "LLMSettings", "detect_provider", "mask", "resolve_settings", "LLMCache",
           "LLMClient", "LLMError", "parse_json_loose", "build_client"]


def _key_chain(key=None) -> list[str]:
    """Primary key + fallbacks. LLM_API_KEY may hold several comma-separated keys, and
    LLM_FALLBACK_API_KEYS adds more. Order = priority."""
    import os
    raw = [key] if key else [os.environ.get("LLM_API_KEY", "")]
    raw.append(os.environ.get("LLM_FALLBACK_API_KEYS", ""))
    keys = []
    for chunk in raw:
        for k in (chunk or "").split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
    return keys


def build_client(cfg: dict, key=None, provider=None, model=None, base_url=None):
    """Return an LLM client (a FallbackLLM when several keys are configured) or None
    when no key is configured / the LLM is disabled. Never raises."""
    enabled = cfg.get("llm", {}).get("enabled", "auto")
    if enabled is False or str(enabled).lower() in ("false", "off", "no"):
        return None
    lc = cfg.get("llm", {})
    from pathlib import Path
    from ..config import ROOT
    from .providers import FallbackLLM
    cache_dir = Path(lc.get("cache_dir", ".cache/llm"))
    if not cache_dir.is_absolute():
        cache_dir = ROOT / cache_dir
    cache = LLMCache(cache_dir)
    keys = _key_chain(key) or [None]
    clients = []
    for i, k in enumerate(keys):
        # explicit provider/model/base_url apply to the primary key; fallbacks are auto-detected
        s = resolve_settings(key=k, provider=provider if i == 0 else None, model=model if i == 0 else None,
                             base_url=base_url if i == 0 else None) if k else resolve_settings(provider=provider, model=model, base_url=base_url)
        if s.enabled:
            try:
                clients.append(LLMClient(s, cache=cache, timeout=float(lc.get("timeout_seconds", 60)),
                                         temperature=float(lc.get("temperature", 0.2)), max_tokens=int(lc.get("max_output_tokens", 2048))))
            except Exception:  # noqa: BLE001
                continue
    if not clients:
        return None
    return clients[0] if len(clients) == 1 else FallbackLLM(clients)

"""One key -> any LLM.

Set LLM_API_KEY and nothing else: the provider is recognised from the key's
prefix, the endpoint is filled in, and the model is discovered from the
provider's own /models list (so a retired model name never breaks the tool).

Optional overrides (only when you need them):
    LLM_PROVIDER   force a provider (e.g. mistral, together, ollama, custom)
    LLM_MODEL      force a model id
    LLM_BASE_URL   any OpenAI-compatible endpoint (vLLM, LM Studio, a company gateway)

Recognised key prefixes
    AIza… / AQ.… Google Gemini          gsk_…      Groq
    sk-ant-…     Anthropic Claude       sk-or-…    OpenRouter
    sk-proj-…/sk-…  OpenAI              xai-…      xAI Grok
    nvapi-…      NVIDIA NIM             fw_…       Fireworks
    hf_…         Hugging Face router    csk-…      Cerebras
    tgp_v1_…     Together               sk-<32 hex> DeepSeek
    "ollama"     local Ollama (no key)  "mock"     offline deterministic mock (tests/demo)
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

LEGACY_ENV = ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
              "OPENROUTER_API_KEY", "XAI_API_KEY", "DEEPSEEK_API_KEY", "MISTRAL_API_KEY", "TOGETHER_API_KEY"]


@dataclass
class ProviderSpec:
    name: str
    api: str                        # openai | anthropic | gemini | mock
    base_url: str
    default_model: str
    prefer: list[str] = field(default_factory=list)   # regexes, first match wins during discovery
    free_tier: bool = False


PROVIDERS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec("gemini", "gemini", "https://generativelanguage.googleapis.com/v1beta", "gemini-2.5-flash",
                           [r"^gemini-\d+(\.\d+)?-flash$", r"^gemini-\d+(\.\d+)?-flash-\d+$", r"^gemini-.*flash(?!.*(lite|image|tts|live|audio|thinking|exp|preview))"], True),
    "groq": ProviderSpec("groq", "openai", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile",
                         [r"^llama-3\.3-70b-versatile$", r"^openai/gpt-oss-120b$", r"llama.*70b"], True),
    "openai": ProviderSpec("openai", "openai", "https://api.openai.com/v1", "gpt-4o-mini",
                           [r"^gpt-4o-mini$", r"^gpt-4\.1-mini$", r"^gpt-5-mini$", r"^gpt-4o$"]),
    "anthropic": ProviderSpec("anthropic", "anthropic", "https://api.anthropic.com/v1", "claude-3-5-haiku-latest",
                              [r"haiku", r"sonnet"]),
    "openrouter": ProviderSpec("openrouter", "openai", "https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free",
                               [r"llama-3\.3-70b-instruct:free$", r"gemini.*flash.*:free$", r":free$"], True),
    "xai": ProviderSpec("xai", "openai", "https://api.x.ai/v1", "grok-3-mini", [r"grok-.*mini", r"^grok"]),
    "deepseek": ProviderSpec("deepseek", "openai", "https://api.deepseek.com/v1", "deepseek-chat", [r"^deepseek-chat$"]),
    "mistral": ProviderSpec("mistral", "openai", "https://api.mistral.ai/v1", "mistral-small-latest", [r"^mistral-small-latest$"], True),
    "together": ProviderSpec("together", "openai", "https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo", [r"Llama-3\.3-70B-Instruct-Turbo"]),
    "fireworks": ProviderSpec("fireworks", "openai", "https://api.fireworks.ai/inference/v1", "accounts/fireworks/models/llama-v3p3-70b-instruct", []),
    "nvidia": ProviderSpec("nvidia", "openai", "https://integrate.api.nvidia.com/v1", "meta/llama-3.3-70b-instruct", [r"llama-3\.3-70b-instruct"], True),
    "huggingface": ProviderSpec("huggingface", "openai", "https://router.huggingface.co/v1", "meta-llama/Llama-3.3-70B-Instruct", [], True),
    "cerebras": ProviderSpec("cerebras", "openai", "https://api.cerebras.ai/v1", "llama-3.3-70b", [r"llama-3\.3-70b", r"llama"], True),
    "ollama": ProviderSpec("ollama", "openai", "http://localhost:11434/v1", "llama3.1", [r"llama3", r"qwen", r"mistral"], True),
    "custom": ProviderSpec("custom", "openai", "", "default", []),
    "mock": ProviderSpec("mock", "mock", "", "mock-judge-1", [], True),
}

KEY_PREFIXES: list[tuple[str, str]] = [
    ("sk-ant-", "anthropic"), ("sk-or-", "openrouter"), ("AIza", "gemini"), ("AQ.", "gemini"), ("gsk_", "groq"),
    ("xai-", "xai"), ("nvapi-", "nvidia"), ("fw_", "fireworks"), ("hf_", "huggingface"),
    ("csk-", "cerebras"), ("tgp_v1_", "together"), ("sk-proj-", "openai"), ("sk-svcacct-", "openai"),
]


def detect_provider(key: Optional[str]) -> Optional[str]:
    """Return the provider name for a key, or None when the key is unknown/empty."""
    if not key:
        return None
    k = key.strip()
    low = k.lower()
    if low in ("mock", "test", "demo-mock"):
        return "mock"
    if low in ("ollama", "local"):
        return "ollama"
    for prefix, name in KEY_PREFIXES:
        if k.startswith(prefix):
            return name
    if re.fullmatch(r"sk-[0-9a-f]{32}", k):
        return "deepseek"
    if k.startswith("sk-"):
        return "openai"
    return None


def unknown_key_hint(key: Optional[str]) -> str:
    """Explain what to do when a key's prefix is not recognised."""
    if not key:
        return "No key found. Put LLM_API_KEY=... in .env (any supported provider)."
    return ("The key's prefix was not recognised. Tell the tool which provider it belongs to, e.g. add "
            "LLM_PROVIDER=gemini (or groq, openai, anthropic, openrouter, mistral, together, …) to .env, "
            "or set LLM_BASE_URL for any OpenAI-compatible endpoint.")


def mask(key: Optional[str]) -> str:
    if not key:
        return ""
    k = key.strip()
    return (k[:4] + "…" + k[-4:]) if len(k) > 10 else "…"


@dataclass
class LLMSettings:
    key: Optional[str]
    provider: Optional[str]
    model: Optional[str]
    base_url: Optional[str]
    source: str = "env"

    @property
    def enabled(self) -> bool:
        return self.provider is not None

    def describe(self) -> dict:
        spec = PROVIDERS.get(self.provider or "", None)
        return {"enabled": self.enabled, "provider": self.provider, "model": self.model or (spec.default_model if spec else None),
                "key": mask(self.key), "base_url": self.base_url or (spec.base_url if spec else None),
                "free_tier": bool(spec and spec.free_tier)}


def resolve_settings(key: Optional[str] = None, provider: Optional[str] = None, model: Optional[str] = None,
                     base_url: Optional[str] = None) -> LLMSettings:
    """Explicit arguments > LLM_* env vars > legacy provider env vars."""
    source = "argument" if key else "env"
    key = key or os.environ.get("LLM_API_KEY")
    if not key:
        for env in LEGACY_ENV:
            if os.environ.get(env):
                key = os.environ[env]
                source = env
                break
    provider = provider or os.environ.get("LLM_PROVIDER") or None
    model = model or os.environ.get("LLM_MODEL") or None
    base_url = base_url or os.environ.get("LLM_BASE_URL") or None
    if provider:
        provider = provider.strip().lower()
        if provider in ("none", "off", "rules"):
            return LLMSettings(None, None, None, None, "disabled")
        if provider not in PROVIDERS:
            provider = "custom"
    else:
        provider = detect_provider(key)
        if provider is None and base_url:
            provider = "custom"
    if provider == "custom" and not base_url:
        provider = None
    return LLMSettings(key=key, provider=provider, model=model, base_url=base_url, source=source)

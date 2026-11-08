"""HTTP clients for the three API shapes that cover every provider:
OpenAI-compatible chat completions, Anthropic messages, Gemini generateContent.
Plus a deterministic offline mock for tests and demos.

No vendor SDKs: plain httpx keeps the dependency list tiny and the swap trivial.
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Optional

import httpx

from .base import PROVIDERS, LLMSettings, ProviderSpec
from .cache import LLMCache


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: LLMSettings, cache: Optional[LLMCache] = None, timeout: float = 60.0,
                 temperature: float = 0.2, max_tokens: int = 2048):
        if not settings.enabled:
            raise LLMError("LLM is not configured (set LLM_API_KEY).")
        self.settings = settings
        self.spec: ProviderSpec = PROVIDERS[settings.provider]
        self.base_url = (settings.base_url or self.spec.base_url).rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.cache = cache
        self._model: Optional[str] = settings.model
        self._lock = threading.Lock()
        self.stats = {"calls": 0, "cache_hits": 0, "input_tokens": 0, "output_tokens": 0, "errors": 0, "retries": 0}

    # ------------------------------------------------------------ model
    @property
    def model(self) -> str:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = self._discover_model()
        return self._model

    def _discover_model(self) -> str:
        if self.spec.api == "mock":
            return self.spec.default_model
        try:
            ids = self.list_models()
        except Exception:
            return self.spec.default_model
        if self.spec.default_model in ids:
            return self.spec.default_model
        for pat in self.spec.prefer:
            matches = [m for m in ids if re.search(pat, m)]
            if matches:
                def ver(m):
                    nums = re.findall(r"\d+(?:\.\d+)?", m)
                    return [float(x) for x in nums[:2]] or [0.0]
                return sorted(matches, key=ver, reverse=True)[0] if self.spec.api == "gemini" else matches[0]
        return ids[0] if ids else self.spec.default_model

    def list_models(self) -> list[str]:
        key = self.settings.key or ""
        with httpx.Client(timeout=10) as c:
            if self.spec.api == "gemini":
                r = c.get(f"{self.base_url}/models", headers={"x-goog-api-key": key}, params={"pageSize": 200})
                if r.status_code in (400, 401, 403):
                    r = c.get(f"{self.base_url}/models", params={"pageSize": 200, "key": key})
                r.raise_for_status()
                return [m["name"].split("/", 1)[-1] for m in r.json().get("models", [])
                        if "generateContent" in m.get("supportedGenerationMethods", [])]
            if self.spec.api == "anthropic":
                r = c.get(f"{self.base_url}/models", headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
                r.raise_for_status()
                return [m["id"] for m in r.json().get("data", [])]
            headers = {"Authorization": f"Bearer {key}"} if key and key.lower() not in ("ollama", "local") else {}
            r = c.get(f"{self.base_url}/models", headers=headers)
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", [])]

    # ------------------------------------------------------------ call
    def complete_json(self, system: str, user: str) -> dict:
        """Send a prompt, get a parsed JSON object back (cached, retried)."""
        ck = None
        if self.cache:
            ck = self.cache.key(self.settings.provider, self.model, system, user)
            hit = self.cache.get(ck)
            if hit is not None:
                self.stats["cache_hits"] += 1
                return hit
        text = self._call_with_retry(system, user)
        data = parse_json_loose(text)
        if self.cache and ck:
            self.cache.set(ck, data)
        return data

    def _call_with_retry(self, system: str, user: str, attempts: int = 4) -> str:
        delay = 2.0
        last_exc: Optional[Exception] = None
        for a in range(attempts):
            try:
                return self._call(system, user)
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                last_exc = exc
                if code in (429, 500, 502, 503, 504, 529) and a < attempts - 1:
                    self.stats["retries"] += 1
                    ra = exc.response.headers.get("retry-after")
                    time.sleep(float(ra) if ra and ra.replace(".", "").isdigit() else delay)
                    delay *= 2
                    continue
                self.stats["errors"] += 1
                body = exc.response.text[:300]
                raise LLMError(f"{self.settings.provider} HTTP {code}: {body}") from exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if a < attempts - 1:
                    self.stats["retries"] += 1
                    time.sleep(delay)
                    delay *= 2
                    continue
                self.stats["errors"] += 1
                raise LLMError(f"{self.settings.provider} network error: {exc}") from exc
        raise LLMError(str(last_exc))

    def _call(self, system: str, user: str) -> str:
        self.stats["calls"] += 1
        api = self.spec.api
        if api == "mock":
            return mock_response(user)
        key = self.settings.key or ""
        with httpx.Client(timeout=self.timeout) as c:
            if api == "gemini":
                body = {"systemInstruction": {"parts": [{"text": system}]},
                        "contents": [{"role": "user", "parts": [{"text": user}]}],
                        "generationConfig": {"temperature": self.temperature, "maxOutputTokens": self.max_tokens,
                                             "responseMimeType": "application/json"}}
                d = self._gemini_post(c, key, body)
                um = d.get("usageMetadata", {})
                self._usage(um.get("promptTokenCount", 0), um.get("candidatesTokenCount", 0))
                parts = (d.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts)
            if api == "anthropic":
                r = c.post(f"{self.base_url}/messages",
                           headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                           json={"model": self.model, "max_tokens": self.max_tokens, "temperature": self.temperature,
                                 "system": system, "messages": [{"role": "user", "content": user}]})
                r.raise_for_status()
                d = r.json()
                u = d.get("usage", {})
                self._usage(u.get("input_tokens", 0), u.get("output_tokens", 0))
                return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
            # OpenAI-compatible
            headers = {"Content-Type": "application/json"}
            if key and key.lower() not in ("ollama", "local"):
                headers["Authorization"] = f"Bearer {key}"
            body = {"model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "response_format": {"type": "json_object"}}
            r = c.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            if r.status_code == 400 and "response_format" in r.text:
                body.pop("response_format")          # some providers do not support JSON mode
                r = c.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            d = r.json()
            u = d.get("usage", {}) or {}
            self._usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            return d["choices"][0]["message"].get("content") or ""

    # Google keys come in two shapes (classic AIza…, newer AQ.… auth keys) and some keys are only enabled on
    # one Google endpoint. Try the documented route first, then the alternatives; remember the one that works.
    def _gemini_routes(self, key: str):
        base = self.base_url
        model = self.model
        return [
            ("ai-studio header", f"{base}/models/{model}:generateContent", {"x-goog-api-key": key}, {}),
            ("ai-studio query", f"{base}/models/{model}:generateContent", {}, {"key": key}),
            ("vertex express", f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent", {}, {"key": key}),
        ]

    def _gemini_post(self, c: httpx.Client, key: str, body: dict) -> dict:
        routes = self._gemini_routes(key)
        if getattr(self, "_gemini_route", None) is not None:
            routes = [r for r in routes if r[0] == self._gemini_route] + [r for r in routes if r[0] != self._gemini_route]
        last: Optional[httpx.HTTPStatusError] = None
        for name, url, headers, params in routes:
            r = c.post(url, headers={**headers, "Content-Type": "application/json"}, params=params or None, json=body)
            if r.status_code in (400, 401, 403, 404) and name != routes[-1][0]:
                # auth/route mismatch (or model not on this endpoint): try the next route
                last = httpx.HTTPStatusError(f"{name}: HTTP {r.status_code}", request=r.request, response=r)
                continue
            r.raise_for_status()
            self._gemini_route = name
            self.stats["gemini_route"] = name
            return r.json()
        if last is not None:
            raise last
        raise LLMError("no Gemini route succeeded")

    def _usage(self, i: int, o: int):
        with self._lock:
            self.stats["input_tokens"] += int(i or 0)
            self.stats["output_tokens"] += int(o or 0)

    def ping(self) -> dict:
        out = self.complete_json("Reply with JSON only.", 'Return {"ok": true, "note": "pong"}')
        return {"provider": self.settings.provider, "model": self.model, "response": out}


def parse_json_loose(text: str) -> dict:
    """Parse model output that should be JSON but may be wrapped in prose or ``` fences."""
    if not text:
        raise LLMError("empty response")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        v = json.loads(t)
        return v if isinstance(v, dict) else {"results": v}
    except json.JSONDecodeError:
        pass
    m = re.search(r"(\{.*\}|\[.*\])", t, re.S)
    if m:
        frag = re.sub(r",\s*([}\]])", r"\1", m.group(1))   # trailing commas
        try:
            v = json.loads(frag)
            return v if isinstance(v, dict) else {"results": v}
        except json.JSONDecodeError:
            pass
    raise LLMError(f"could not parse JSON from model output: {text[:200]}")


def mock_response(user: str) -> str:
    """Deterministic stand-in for a model: scores candidates from cue words in the transcript."""
    results = []
    for block in re.split(r"\n(?=### CANDIDATE )", user):
        m = re.match(r"### CANDIDATE (\S+)", block)
        if not m:
            continue
        cid = m.group(1)
        clip = block.split("CLIP:", 1)[-1].split("AFTER THE CUT:", 1)[0]
        lines = [ln for ln in clip.splitlines() if re.match(r"\s*L\d+", ln)]
        low = clip.lower()
        hook = 9 if re.search(r"slap|throws|grabs|pregnant|heir|secret", low) else 5
        cliff = 8 if lines and re.search(r"(\?|—|\.\.\.|turns|freezes|door|who)", lines[-1].lower()) else 4
        sa = 8 if not re.search(r"\b(again|remember|last night|earlier)\b", low) else 5
        overall = round((hook * 0.4 + cliff * 0.35 + sa * 0.25), 1)
        first = int(re.match(r"\s*L(\d+)", lines[0]).group(1)) if lines else 1
        last = int(re.match(r"\s*L(\d+)", lines[-1]).group(1)) if lines else 1
        results.append({"id": cid, "hook_score": hook, "cliffhanger_score": cliff, "standalone_score": sa,
                        "overall": overall, "hook": "Mock: opening beat", "cliffhanger": "Mock: final beat",
                        "why": "Mock judge: scored from cue words.", "start_line": first, "end_line": last,
                        "red_flags": []})
    return json.dumps({"results": results})


class FallbackLLM:
    """Several clients behind one interface: if the active provider fails (bad key, quota, outage),
    the next key is tried. A provider that fails twice in a row is skipped for the rest of the run
    (circuit breaker)."""

    def __init__(self, clients: list[LLMClient]):
        if not clients:
            raise LLMError("no LLM clients")
        self.clients = clients
        self.failures = [0] * len(clients)
        self.active = 0
        self._lock = threading.Lock()
        self.switches: list[str] = []

    # attributes the rest of the code reads
    @property
    def settings(self):
        return self.clients[self.active].settings

    @property
    def spec(self):
        return self.clients[self.active].spec

    @property
    def _model(self):
        return self.clients[self.active]._model

    @property
    def model(self) -> str:
        return self.clients[self.active].model

    @property
    def stats(self) -> dict:
        tot: dict = {}
        for c in self.clients:
            for k, v in c.stats.items():
                if isinstance(v, (int, float)):
                    tot[k] = tot.get(k, 0) + v
                else:
                    tot[k] = v
        tot["providers_tried"] = sum(1 for c in self.clients if c.stats["calls"] or c.stats["cache_hits"])
        tot["switches"] = len(self.switches)
        return tot

    def complete_json(self, system: str, user: str) -> dict:
        last: Optional[Exception] = None
        for idx in list(range(self.active, len(self.clients))) + list(range(0, self.active)):
            if self.failures[idx] >= 2:
                continue
            try:
                out = self.clients[idx].complete_json(system, user)
                with self._lock:
                    self.failures[idx] = 0
                    if idx != self.active:
                        self.switches.append(f"{self.clients[self.active].settings.provider} -> {self.clients[idx].settings.provider}")
                        self.active = idx
                return out
            except Exception as exc:  # noqa: BLE001
                last = exc
                with self._lock:
                    self.failures[idx] += 1
        raise LLMError(f"all LLM providers failed; last error: {last}")

    def ping(self) -> dict:
        return {"provider": self.settings.provider, "model": self.model,
                "response": self.complete_json("Reply with JSON only.", 'Return {"ok": true}'),
                "chain": [c.settings.provider for c in self.clients]}

"""Configuration loading: default.yaml + optional user override + learned weights + env."""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DEFAULT_CONFIG = CONFIG_DIR / "default.yaml"
LEXICON_FILE = CONFIG_DIR / "lexicons.yaml"
LEARNED_WEIGHTS = CONFIG_DIR / "learned_weights.yaml"


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


_LOAD_WARNINGS: list[str] = []


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError) as exc:
        _LOAD_WARNINGS.append(f"Could not read {path.name} ({exc}); using built-in defaults.")
        return {}


def load_warnings() -> list[str]:
    """Config problems found so far (reported in every run's warnings)."""
    return list(dict.fromkeys(_LOAD_WARNINGS))


def load_config(path: Optional[str | Path] = None, overrides: Optional[dict] = None) -> dict[str, Any]:
    from .defaults import DEFAULT_CONFIG as BUILTIN
    # built-in copy first, YAML on top: a missing/partial/corrupt file can never remove a required key
    cfg = deep_merge(BUILTIN, _read_yaml(DEFAULT_CONFIG))
    if not DEFAULT_CONFIG.exists():
        _LOAD_WARNINGS.append("config/default.yaml not found; using built-in defaults.")
    if path:
        cfg = deep_merge(cfg, _read_yaml(Path(path)))
    if cfg.get("use_learned_weights") and LEARNED_WEIGHTS.exists():
        learned = _read_yaml(LEARNED_WEIGHTS).get("weights", {})
        learned = {k: float(v) for k, v in learned.items()
                   if k in cfg["weights"] and isinstance(v, (int, float)) and 0 <= float(v) <= 5}
        if learned and sum(learned.values()) > 0:
            cfg["weights"] = deep_merge(cfg["weights"], learned)
            cfg["_weights_source"] = "learned"
    cfg.setdefault("_weights_source", "default")
    if overrides:
        cfg = deep_merge(cfg, overrides)
    # Writable cache location (Vercel only allows /tmp)
    if os.environ.get("VERCEL") or os.environ.get("PROMO_READONLY_FS"):
        cfg["llm"]["cache_dir"] = "/tmp/promo-cache/llm"
    return cfg


def apply_platform(cfg: dict, platform: Optional[str]) -> dict:
    if not platform or platform == "any":
        preset = cfg.get("platforms", {}).get("any")
    else:
        preset = cfg.get("platforms", {}).get(platform)
        if preset is None:
            raise ValueError(f"Unknown platform '{platform}'. Choose from: {', '.join(cfg.get('platforms', {}))}")
    if preset:
        cfg = deep_merge(cfg, {"promo": preset})
    cfg["_platform"] = platform or "any"
    return cfg


def load_lexicons(path: Optional[Path] = None) -> dict[str, Any]:
    from .defaults import DEFAULT_LEXICONS
    data = _read_yaml(path or LEXICON_FILE)
    if not data.get("hook") or not data.get("cliffhanger"):
        if (path or LEXICON_FILE).exists():
            _LOAD_WARNINGS.append("lexicons.yaml is incomplete; using the built-in lexicon.")
        return copy.deepcopy(DEFAULT_LEXICONS)
    return data

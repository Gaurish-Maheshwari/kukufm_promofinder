import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).parent / "fixtures"
SAMPLE = ROOT / "data" / "sample"


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIX


@pytest.fixture(scope="session")
def sample_dir() -> Path:
    if not (SAMPLE / "sample_show.zip").exists():
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_sample_data.py")], check=True)
    return SAMPLE


@pytest.fixture(scope="session")
def sample_run(sample_dir):
    from promo_engine.pipeline import run_pipeline
    return run_pipeline(sample_dir / "sample_show.zip", manual=sample_dir / "manual_promos_sample.csv", use_llm=False,
                        show_title="Sample")


@pytest.fixture(autouse=True)
def _no_llm_env(monkeypatch):
    for k in ("LLM_API_KEY", "LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY",
              "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)

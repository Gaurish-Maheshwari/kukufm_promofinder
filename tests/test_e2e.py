"""End-to-end: the CLI on the sample zip, exactly as a user would run it."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_cli_run_end_to_end(sample_dir, tmp_path):
    out = tmp_path / "run"
    cmd = [sys.executable, "-m", "promo_engine", "run", "-i", str(sample_dir / "sample_show.zip"),
           "-m", str(sample_dir / "manual_promos_sample.csv"), "-o", str(out), "--quiet", "--no-llm"]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    assert "The tool found" in res.stdout
    run = json.loads((out / "promos.json").read_text())
    assert run["metrics"]["brief_compliance"]["duration_in_range"] == 1.0
    assert run["metrics"]["agreement_with_manual"]["recall"] >= 0.8


def test_cli_parse(sample_dir):
    res = subprocess.run([sys.executable, "-m", "promo_engine", "parse", "-i", str(sample_dir / "show")],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0 and "8 episode(s)" in res.stdout


def test_cli_learn_dry_run(sample_dir):
    res = subprocess.run([sys.executable, "-m", "promo_engine", "learn", "-i", str(sample_dir / "show"),
                          "-m", str(sample_dir / "manual_promos_sample.csv"), "--dry-run"],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    assert "hook" in res.stdout and "auc" in res.stdout

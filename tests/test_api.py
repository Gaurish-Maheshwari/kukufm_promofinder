import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from backend.app import app
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health").json()
    assert r["ok"] and "llm" in r and r["llm"]["key"] == ""


def test_sample_and_stateless_exports(client):
    run = client.post("/api/analyze/sample", json={"with_manual": True}).json()
    assert run["promos"] and run["comparison"]["summary"]["manual_total"] == 10
    for fmt in ("csv", "cutsheet", "md", "html", "edl", "markers", "ffmpeg", "json", "comparison"):
        r = client.post(f"/api/export/{fmt}", json=run)
        assert r.status_code == 200 and len(r.content) > 50, fmt
        assert "attachment" in r.headers["content-disposition"]
    assert client.post("/api/export/nope", json=run).status_code == 404


def test_upload_job_flow(client, sample_dir):
    files = [("files", ("show/Episode_01.txt", (sample_dir / "show" / "Episode_01.txt").read_bytes())),
             ("files", ("show/Episode_02.txt", (sample_dir / "show" / "Episode_02.txt").read_bytes()))]
    job = client.post("/api/jobs", files=files, data={"options": '{"platform": "reels", "top_k": 5}'}).json()
    for _ in range(40):
        j = client.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert j["status"] == "done", j
    assert 0 < len(j["result"]["promos"]) <= 5
    assert all(25 - 0.5 <= p["duration"] <= 45.5 for p in j["result"]["promos"])


def test_bad_inputs(client):
    r = client.post("/api/analyze", files=[("files", ("photo.png", b"\x89PNG"))])
    assert r.status_code == 422
    r = client.post("/api/analyze", files=[("files", ("a.txt", b"x"))], data={"options": "{not json"})
    assert r.status_code == 422


def test_server_path_is_sandboxed(client):
    assert client.post("/api/analyze/path", json={"path": "data/sample/show"}).status_code == 200
    assert client.post("/api/analyze/path", json={"path": "/etc"}).status_code == 403
    assert client.post("/api/analyze/path", json={"path": "data/../../etc"}).status_code == 403


def test_llm_check_masks_key(client):
    r = client.post("/api/llm/check", json={"key": "gsk_SECRETSECRETSECRET1234"}).json()
    assert r["detected"]["provider"] == "groq" and "SECRET" not in str(r)


def test_feedback_roundtrip(client, tmp_path, monkeypatch):
    import backend.storage as st
    monkeypatch.setattr(st, "FEEDBACK_FILE", tmp_path / "fb.jsonl")
    r = client.post("/api/feedback", json={"run_id": "x", "promo_id": "P01", "verdict": "accept"})
    assert r.json()["stored"] == 1
    assert client.get("/api/feedback").json()[0]["verdict"] == "accept"

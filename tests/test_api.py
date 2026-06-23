"""Integration tests for the HTTP API.

The translation + TTS pipeline is mocked, so these tests run fully offline and
CPU-only — they exercise the FastAPI routing, request validation, response
shapes, and header encoding without synthesizing real audio.
"""

import base64
import json
import socket
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from basha.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# /synthesize
# ---------------------------------------------------------------------------
@patch("basha.api.routes.orchestrator.process")
def test_synthesize_returns_audio(mock_process):
    mock_process.return_value = (b"FAKE_MP3_BYTES", {"rtf": 0.2})
    resp = client.post(
        "/synthesize",
        json={"text": "Hello", "target_language": "de", "backend": "gtts"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"FAKE_MP3_BYTES"


@patch("basha.api.routes.orchestrator.process")
def test_synthesize_empty_audio_is_client_error(mock_process):
    # Pipeline produced nothing -> the route raises a 400 (not masked as 500).
    mock_process.return_value = (b"", {})
    resp = client.post("/synthesize", json={"text": "Hello", "target_language": "de"})
    assert resp.status_code == 400
    assert "Failed to generate audio" in resp.json()["detail"]


def test_synthesize_rejects_missing_text():
    # Pydantic validation: 'text' is required.
    resp = client.post("/synthesize", json={"target_language": "de"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /scene
# ---------------------------------------------------------------------------
@patch("basha.api.routes.orchestrator.process_scene")
def test_scene_populates_headers(mock_scene):
    transcript = [{"speaker": "Ravi", "text": "नमस्ते"}]  # non-ASCII on purpose
    cast = {"Ravi": "hi-IN-MadhavNeural"}
    metrics = {"rtf": 0.3, "total_chunks": 2}
    mock_scene.return_value = (b"SCENE_MP3", cast, transcript, metrics)

    resp = client.post(
        "/scene",
        json={"script": "Ravi: Hello", "target_language": "hi", "translate": True},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert json.loads(resp.headers["X-Cast"]) == cast
    assert json.loads(resp.headers["X-Metrics"]) == metrics

    # X-Script is base64-encoded UTF-8 JSON (HTTP headers can't carry raw Telugu/Hindi).
    decoded = json.loads(base64.b64decode(resp.headers["X-Script"]).decode("utf-8"))
    assert decoded == transcript


@patch("basha.api.routes.orchestrator.process_scene")
def test_scene_empty_audio_is_client_error(mock_scene):
    mock_scene.return_value = (b"", {}, [], {})
    resp = client.post("/scene", json={"script": "Ravi: Hello", "target_language": "hi"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /cache
# ---------------------------------------------------------------------------
def test_cache_stats_shape():
    resp = client.get("/cache/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert {"cached_files", "total_mb", "cache_dir"} <= data.keys()
    assert isinstance(data["cached_files"], int)


def test_cache_clear():
    resp = client.delete("/cache")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleared"


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
def test_health_shape():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert {"internet_connected", "cache_writable", "active_engine"} <= data.keys()


def test_health_degraded_without_internet():
    # Replace only the *route's* socket reference so the connectivity probe
    # fails, without disturbing the test client's own (real) sockets.
    fake_socket_module = MagicMock()
    fake_socket_module.AF_INET = socket.AF_INET
    fake_socket_module.SOCK_STREAM = socket.SOCK_STREAM
    fake_socket_module.socket.return_value.connect.side_effect = OSError("no network")

    with patch("basha.api.routes.socket", fake_socket_module):
        resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["internet_connected"] is False
    assert data["status"] in ("degraded", "unhealthy")

"""/categorize-transactions: validation, gating, and output sanitising (LLM mocked)."""
import os
import sys

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("slowapi")

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")


def _import_server():
    """Import backend/server.py with Google Cloud SDKs stubbed (OCR/Firestore aren't exercised)."""
    import types
    from unittest import mock
    os.environ.setdefault("ALLOW_INSECURE_JWT_SECRET", "1")
    os.environ.setdefault("AI_API_KEY", "test-key")
    sys.path.insert(0, os.path.abspath(BACKEND))
    for name in ("google.cloud.vision", "google.cloud.firestore"):
        try:
            __import__(name)
        except Exception:
            parent = sys.modules.setdefault("google.cloud", types.ModuleType("google.cloud"))
            stub = mock.MagicMock(name=name)
            sys.modules[name] = stub
            setattr(parent, name.rsplit(".", 1)[1], stub)
    import server
    return server


@pytest.fixture(scope="module")
def client():
    try:
        server = _import_server()
    except SyntaxError:
        raise  # a broken backend file must fail, not skip
    except Exception as exc:  # missing deps on a dev box
        pytest.skip(f"backend not importable here: {exc}")
    from fastapi.testclient import TestClient
    server.app.dependency_overrides[server.require_pro] = lambda: {"features": ["advanced_categorization"]}
    yield TestClient(server.app), server
    server.app.dependency_overrides.clear()


def test_maps_ids_and_clamps_unknown_categories(client, monkeypatch):
    c, server = client
    import ai
    monkeypatch.setattr(ai, "_chat", lambda *a, **k:
                        'Sure! {"0": "dining", "1": "Spaceships", "7": "Dining"}')
    r = c.post("/categorize-transactions", json={
        "items": [{"i": 0, "merchant": "Joe's", "amount": -9}, {"i": 1, "merchant": "Zzq", "amount": -60}],
        "categories": ["Dining", "Groceries"]})
    assert r.status_code == 200
    assert r.json() == {"categories": {"0": "Dining", "1": "Other"}}


def test_garbage_reply_is_empty_not_500(client, monkeypatch):
    c, _ = client
    import ai
    monkeypatch.setattr(ai, "_chat", lambda *a, **k: "I cannot do that")
    r = c.post("/categorize-transactions", json={"items": [{"i": 0, "merchant": "x", "amount": -1}]})
    assert r.status_code == 200 and r.json() == {"categories": {}}


def test_rejects_oversized_batches(client):
    c, _ = client
    items = [{"i": i, "merchant": "m", "amount": -1} for i in range(101)]
    assert c.post("/categorize-transactions", json={"items": items}).status_code == 422


def test_requires_a_licence():
    try:
        server = _import_server()
    except Exception as exc:
        pytest.skip(f"backend not importable here: {exc}")
    from fastapi.testclient import TestClient
    saved = dict(server.app.dependency_overrides)
    server.app.dependency_overrides.clear()
    try:
        r = TestClient(server.app).post("/categorize-transactions",
                                        json={"items": [{"i": 0, "merchant": "x", "amount": -1}]})
        assert r.status_code in (401, 403)
    finally:
        server.app.dependency_overrides.update(saved)


def test_advanced_categorize_falls_back_without_crewai(client, monkeypatch):
    """On Vercel CrewAI isn't installed; one LLM call returns the same report shape."""
    c, _ = client
    import ai
    monkeypatch.setitem(sys.modules, "bots", None)  # makes `from bots import ...` raise ImportError
    monkeypatch.setattr(ai, "_chat", lambda *a, **k:
                        '{"summary": "ok", "key_findings": ["a"], "anomalies": [], "recommendations": ["b"]}')
    r = c.post("/advanced-categorize", json={"expenses": [{"name": "Coffee", "price": 4, "category": "Food"}]})
    assert r.status_code == 200
    assert r.json() == {"summary": "ok", "key_findings": ["a"], "anomalies": [], "recommendations": ["b"]}


def test_ip_limiter_fails_open_without_any_store(monkeypatch):
    sys.path.insert(0, os.path.abspath(BACKEND))
    import ip_limits
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(ip_limits, "_get_client", lambda: None)
    assert ip_limits.check_and_register_ip({"tier": "pro", "jti": "x"}, "1.2.3.4") == (True, 0, 3)

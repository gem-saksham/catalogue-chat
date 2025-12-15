from fastapi.testclient import TestClient
import pytest

import sys
from pathlib import Path

pytest.importorskip("langchain_community")
pytest.importorskip("langchain_ollama")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.api.main import app
from app.rag.langchain_rag import RagHit


def test_rag_endpoint_uses_langchain_pipeline(monkeypatch):
    class FakeRag:
        def invoke(self, question: str, k: int | None = None):
            meta = {"title": "T", "record_id": "1", "url": "u", "label": "metadata", "chunk": 0}
            return "answer", [RagHit(text="ctx", score=0.9, metadata=meta)]

    monkeypatch.setattr("app.api.main.rag_pipeline", FakeRag())

    client = TestClient(app)
    resp = client.post("/rag", json={"query": "hello", "k": 2})
    assert resp.status_code == 200
    data = resp.json()

    assert data["query"] == "hello"
    assert data["answer"] == "answer"
    assert len(data["contexts"]) == 1
    assert data["contexts"][0]["score"] == 0.9
    assert data["contexts"][0]["source"]["title"] == "T"


def test_rag_endpoint_returns_503_when_pipeline_missing(monkeypatch):
    monkeypatch.setattr("app.api.main.rag_pipeline", None)
    monkeypatch.setattr("app.api.main._rag_init_error", RuntimeError("boom"))

    client = TestClient(app)
    resp = client.post("/rag", json={"query": "hello", "k": 2})
    assert resp.status_code == 503
    assert resp.json()["detail"].startswith("RAG pipeline unavailable")

import os
from typing import List

from langchain_ollama import OllamaEmbeddings

# FIX: Changed the default OLLAMA_BASE_URL from 'http://ollama:11434' to 'http://localhost:11434'.
# This allows the host-run ingestion script to correctly resolve the Ollama service
# exposed via docker-compose.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")

_embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts using the LangChain Ollama embeddings wrapper."""
    if not texts:
        return []
    return _embeddings.embed_documents(texts)

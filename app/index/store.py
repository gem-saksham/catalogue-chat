import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from chromadb.telemetry.product import posthog as chroma_posthog

# Prefer a repo-local data directory when CHROMA_DIR is not explicitly set, so
# local ingest runs write to a predictable path that the API can read back.
logger = logging.getLogger(__name__)


def _resolve_chroma_dir() -> Path:
    base_dir = Path(__file__).resolve().parents[2]
    raw = (os.environ.get("CHROMA_DIR") or "").strip()

    # Treat empty/whitespace env vars as unset to avoid accidentally pointing at
    # the working directory. Resolve relative paths against the repo root so
    # `CHROMA_DIR=data/chroma` works regardless of where the process starts.
    if not raw:
        return base_dir / "data" / "chroma"

    path = Path(raw)
    return path if path.is_absolute() else (base_dir / path)


CHROMA_DIR = _resolve_chroma_dir()
COLLECTION = os.environ.get("COLLECTION", "catalogue")


def _silence_chroma_telemetry() -> None:
    """Prevent Chroma from calling PostHog with incompatible signatures."""

    def _noop_capture(*_args: Any, **_kwargs: Any) -> None:
        return None

    chroma_posthog.capture = _noop_capture
    if hasattr(chroma_posthog, "client"):
        chroma_posthog.client = None


_silence_chroma_telemetry()


def get_collection():
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("Using Chroma directory", extra={"chroma_dir": str(CHROMA_DIR)})
    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    
    # Use get_or_create_collection, which is safe for both ingest and retrieval.
    coll = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    # --- Start Debugging Additions ---
    # Check and log the number of documents in the collection
    try:
        count = coll.count()
        logger.info("Chroma collection ready", extra={"collection_name": COLLECTION, "count": count})
        if count == 0:
            logger.warning(
                "Chroma collection appears to be empty or data is not visible to the retriever service. "
                "Ensure ingestion wrote data to the correct shared volume."
            )
    except Exception as e:
        logger.error(f"Failed to get collection count for {COLLECTION}: {e}")
    # --- End Debugging Additions ---

    return coll

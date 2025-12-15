import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.rag import LangChainRAG

app = FastAPI(title="catalogue-chat retriever")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Source(BaseModel):
    title: str | None = None
    record_id: str | None = None
    url: str | None = None
    label: str | None = None
    chunk: int | None = None


class Hit(BaseModel):
    text: str
    score: float
    source: Source


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=2)
    k: int = Field(4, ge=1, le=20, description="Number of context chunks to retrieve")


class ChatResponse(BaseModel):
    query: str
    answer: str
    contexts: List[Hit]


rag_pipeline: LangChainRAG | None = None
_rag_init_error: Optional[Exception] = None
try:
    rag_pipeline = LangChainRAG()
except Exception as exc:  # noqa: BLE001 - surface initialization failures clearly
    _rag_init_error = exc
    logger.exception("Failed to initialize LangChain RAG pipeline")



class ChatRequest(BaseModel):
    query: str = Field(..., min_length=2)
    k: int = Field(4, ge=1, le=20, description="Number of context chunks to retrieve")


class ChatResponse(BaseModel):
    query: str
    answer: str
    contexts: List[Hit]


rag_pipeline = LangChainRAG()

@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/rag", response_model=ChatResponse)
def rag_chat(req: ChatRequest):
    logger.info("rag chat request", extra={"query": req.query, "limit": req.k})
    if rag_pipeline is None:
        logger.error("RAG pipeline unavailable", extra={"error": repr(_rag_init_error)})
        raise HTTPException(
            status_code=503,
            detail=(
                "RAG pipeline unavailable. Ensure LangChain dependencies are installed "
                "and the pipeline can initialize successfully."
            ),
        )
    try:
        answer, hits = rag_pipeline.invoke(req.query, k=req.k)
    except Exception:
        logger.exception("LangChain RAG pipeline failed")
        raise HTTPException(status_code=500, detail="RAG generation failed")

    contexts: List[Hit] = []
    for h in hits:
        meta = h.metadata or {}
        src = Source(
            title=meta.get("title"),
            record_id=meta.get("record_id"),
            url=meta.get("url"),
            label=meta.get("label"),
            chunk=meta.get("chunk"),
        )
        contexts.append(Hit(text=h.text, score=h.score, source=src))

    return ChatResponse(query=req.query, answer=answer, contexts=contexts)

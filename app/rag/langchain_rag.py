import logging
import os
from dataclasses import dataclass
from typing import List, Tuple

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.index.embed import EMBED_MODEL, OLLAMA_BASE_URL
from app.index.store import CHROMA_DIR, COLLECTION

logger = logging.getLogger(__name__)

CHAT_MODEL = os.environ.get("CHAT_MODEL", "llama3.1")
DEFAULT_TOP_K = int(os.environ.get("RAG_TOP_K", "4"))


def _build_vectorstore() -> Chroma:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    return Chroma(client=client, collection_name=COLLECTION, embedding_function=embeddings)


def _format_documents(docs) -> str:
    parts: List[str] = []
    for idx, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        title = meta.get("title") or "Untitled"
        url = meta.get("url") or ""
        label = meta.get("label") or ""
        chunk = meta.get("chunk")

        header_bits = [f"[{idx}] {title}"]
        if label:
            header_bits.append(label)
        if chunk is not None:
            header_bits.append(f"chunk {chunk}")
        if url:
            header_bits.append(url)

        header = " · ".join(header_bits)
        body = doc.page_content.strip()
        parts.append(f"{header}\n{body}")
    return "\n\n".join(parts)


@dataclass
class RagHit:
    text: str
    score: float
    metadata: dict


class LangChainRAG:
    def __init__(self, top_k: int = DEFAULT_TOP_K):
        self.top_k = top_k
        self.vectorstore = _build_vectorstore()
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful assistant that answers questions using the provided document excerpts. "
                    "Cite the numbered sources inline like [1], [2] and keep answers concise.",
                ),
                ("human", "Question: {question}\n\nContext:\n{context}"),
            ]
        )
        self.llm = ChatOllama(model=CHAT_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)
        self.output_parser = StrOutputParser()

    def _search(self, question: str, k: int) -> List[Tuple[object, float]]:
        k = max(1, k)
        return self.vectorstore.similarity_search_with_relevance_scores(question, k=k)

    def invoke(self, question: str, k: int | None = None) -> Tuple[str, List[RagHit]]:
        k = k or self.top_k
        docs_and_scores = self._search(question, k)
        docs = [doc for doc, _ in docs_and_scores]
        context = _format_documents(docs)

        chain = (
            {"context": RunnableLambda(lambda _x: context), "question": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | self.output_parser
        )

        answer = chain.invoke(question)

        hits: List[RagHit] = []
        for doc, score in docs_and_scores:
            meta = doc.metadata or {}
            hits.append(RagHit(text=doc.page_content, score=float(score), metadata=meta))

        return answer, hits

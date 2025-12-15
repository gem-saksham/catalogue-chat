\
from __future__ import annotations
from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    """Split long text using LangChain's recursive splitter.

    The splitter walks through increasingly fine-grained separators to keep
    paragraph/line boundaries where possible while maintaining the requested
    chunk size and overlap. This keeps chunking logic aligned with the rest of
    our LangChain-powered stack.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " "],
    )
    return splitter.split_text(text)

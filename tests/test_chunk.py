import pytest

pytest.importorskip("langchain")

from index.chunk import chunk_text


def test_chunk_text_overlap_and_size():
    text = "\n\n".join(
        ["para" + str(i) + " " + ("x" * 100) for i in range(10)]
    )
    chunks = chunk_text(text, chunk_size=250, overlap=30)

    # Should create multiple chunks, each within the size limit
    assert len(chunks) > 1
    assert all(len(c) <= 250 for c in chunks)

    # Overlap tail should appear at the start of the next chunk
    for prev, nxt in zip(chunks, chunks[1:]):
        tail = prev[-30:]
        assert tail in nxt

# catalogue-chat walkthrough (beginner friendly)

This guide explains what each part of the codebase does, how data flows through the system, and how to run or test it locally.

## Big-picture pipeline

```
OAI-PMH (e.g., Zenodo) -> harvest_records -> ingest.py -> parse + chunk + embed -> Chroma vector store -> LangChain RAG FastAPI endpoint
```

- **Harvest**: `harvest_records` pulls metadata from public OAI-PMH endpoints.
- **Parse**: downloaded files (PDF/HTML/plain text) are converted into clean text.
- **Chunk**: long text is split into overlapping chunks using LangChain's recursive splitter.
- **Embed**: the LangChain Ollama embeddings wrapper turns each chunk into a vector.
- **Store**: vectors live in a local Chroma collection for cosine-similarity search.
- **Serve**: `/rag` retrieves context through LangChain and generates an answer with inline citations.

## Visual maps

### Data flow
```mermaid
graph LR
  A[OAI-PMH endpoint] --> B(harvest_records)
  B --> C[ingest.py loop]
  C --> D[parse pdf/html/plain]
  D --> E[chunk_text]
  E --> F[embed_texts (LangChain Ollama)]
  F --> G[get_collection → Chroma]
  G --> H[/rag API]
  H --> I[Client (curl/Open WebUI)]
```

### Code relationships
```mermaid
graph TD
  subgraph harvest
    HR[harvest_records] -->|normalized dicts| ING
  end
  subgraph parse
    PDF[extract_pdf_text]
    HTML[extract_html_text]
  end
  subgraph index
    CHK[chunk_text]
    EMB[embed_texts]
    STO[get_collection]
  end
  ING[ingest.py main] --> PDF
  ING --> HTML
  ING --> CHK
  CHK --> EMB
  EMB --> STO
  STO --> API[/rag handler]
```

## Modules and key functions/classes

| File | What it does | How it works |
| --- | --- | --- |
| `app/harvest/oai_pmh.py` | Pulls and normalizes records from an OAI-PMH source. | Uses `sickle.ListRecords` with optional date/set filters. Parses DataCite/Dublin Core XML with `lxml` to extract title, authors, subjects, description, dates, and URLs. |
| `app/parse/pdf.py` | Extracts text from PDFs. | Reads each page with `pypdf.PdfReader` and concatenates text. Errors on individual pages are skipped so a bad page does not abort the file. |
| `app/parse/html.py` | Extracts readable text from HTML. | `BeautifulSoup` drops scripts/styles, flattens text into newline-separated lines, and removes empty lines. |
| `app/index/chunk.py` | Splits long text into overlapping pieces. | Uses LangChain's `RecursiveCharacterTextSplitter` with paragraph/line-aware separators and configurable `chunk_size`/`overlap` defaults. |
| `app/index/embed.py` | Gets embedding vectors. | Uses LangChain's `OllamaEmbeddings` wrapper to embed each chunk with the configured model (default `nomic-embed-text`). |
| `app/index/store.py` | Opens/creates the Chroma collection. | Uses a persistent Chroma client pointing at `CHROMA_DIR` (default `/data/chroma`) and a collection name from `COLLECTION` env var. |
| `app/api/main.py` | FastAPI app with `/healthz` and `/rag`. | `/rag` delegates retrieval + generation to the LangChain pipeline and returns hits with metadata for citation. |
| `app/rag/langchain_rag.py` | LangChain RAG chain. | Reuses the same Chroma collection through a LangChain `Chroma` vector store, formats retrieved chunks, and feeds them to `ChatOllama` with a prompt that emits inline citations. |
| `app/ingest.py` | End-to-end ingestion CLI. | Reads `sources.yaml`, harvests metadata, optionally downloads Zenodo files, parses them, chunks, embeds, and upserts into Chroma. |

## Local run helper script

For a one-command experience, use `./run_local.sh` (created in this repo). It will:
1. Start Docker services (`docker compose up -d`).
2. Pull the default Ollama models.
3. Ingest a small Zenodo slice (configurable).
4. Perform a sample `/rag` question.

You can rerun it safely; it only appends data to the Chroma store.

## Testing map

We added `pytest`-based tests that show how pieces fit together:
- `tests/test_chunk.py` – chunk sizing/overlap.
- `tests/test_parse.py` – HTML cleanup and PDF extraction basics.
- `tests/test_harvest.py` – OAI-PMH normalization from sample XML (no network).
- `tests/test_rag.py` – `/rag` response shape using a patched LangChain pipeline.

Run all tests with `pytest` from the repo root.

## Core concepts (plain language)

- **OAI-PMH**: a standard API for harvesting metadata from repositories (e.g., Zenodo). We call `ListRecords` to get XML records.
- **Embedding**: turning text into a numeric vector so similarity can be computed. Ollama hosts the embedding model locally.
- **Cosine similarity/distance**: measures how close two vectors are. Chroma returns cosine **distance** (0 = identical).
- **Vector store**: a database optimized for nearest-neighbor search over embeddings. Chroma is used here.
- **Chunking**: splitting long documents so each chunk fits the embedding model context and can be retrieved independently.

## What to try next

- Adjust `sources.yaml` to point at another OAI-PMH set or change harvest dates.
- Tune chunk sizes in `app/index/chunk.py` if your texts are very long or short.
- Swap the embedding model by setting `EMBED_MODEL` in the environment (e.g., `export EMBED_MODEL=all-minilm`).
- Call the `/rag` endpoint from your own UI for retrieval-augmented responses.

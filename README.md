# catalogue-chat (MVP)

This repo is a minimal end-to-end demo:

**Public OAI-PMH catalogue (Zenodo)** → harvest metadata (+ optional fulltext files) → chunk & embed → local vector store (Chroma) → LangChain RAG API (FastAPI) → local chat UI (Open WebUI).

## Quick start

If you are new to this stack, read the step-by-step guide in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for plain-language explanations and diagrams.

### 1) Install Python dependencies (for ingestion/tests)
Use **Python 3.10–3.12**. Some transitive dependencies (e.g., `tokenizers` via ChromaDB or `numpy`) do not publish wheels for Python 3.8/3.7, and very new Python releases (e.g., 3.13/3.14) currently lack prebuilt `onnxruntime` wheels that ChromaDB pulls in, so installs will fail on those interpreters. If you hit build errors on Windows, prefer WSL/Docker or install a supported Python version.

Create a virtual environment if you like:
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

Prefer Conda? Use the provided environment to get a supported Python version (3.10–3.12) and install requirements in one step:
```bash
conda env create -f environment.yml
conda activate catalogue-chat
```
Run `conda env update -f environment.yml` to refresh dependencies later.

Verify your interpreter is supported before installing dependencies:
```bash
python scripts/check_python_version.py
```

Then install dependencies with `python -m pip` (avoids older `pip` wrapper warnings):
```bash
python -m pip install -r requirements.txt
# or: python -m pip install -r requirements-dev.txt   # if you plan to run tests
```

### 2) Start services
```bash
docker compose up -d
```

### 3) Pull local models (recommended defaults)
In another terminal:
```bash
docker exec -it $(docker ps -qf name=ollama) ollama pull llama3.1
docker exec -it $(docker ps -qf name=ollama) ollama pull nomic-embed-text
```

### 4) Ingest from Zenodo OAI-PMH
```bash
python app/ingest.py --source "Zenodo OAI demo" --since 2025-01-01 --limit 50
```

This will:
- harvest OAI-PMH records from `sources.yaml`
- extract metadata
- (optionally) download openly available files if present on record pages
- parse text/PDF
- chunk with LangChain's recursive splitter and embed with LangChain's Ollama embeddings
- store in Chroma under `./data/chroma`

### 5) Ask the LangChain RAG endpoint
The project ships with a LangChain pipeline that wraps the Chroma store and an Ollama chat model (default `CHAT_MODEL=llama3.1`).
Send a question with optional `k` for the number of context chunks:
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the dataset about?","k":4}' \
  http://localhost:8000/rag
```
On Windows `cmd.exe`, avoid the Unix-style backslashes and send it as a single
line instead:
```bat
curl -X POST -H "Content-Type: application/json" -d '{"query":"What is the dataset about?","k":4}' http://localhost:8000/rag
```
The response includes a generated answer plus the retrieved chunks and metadata for citations.

### 6) Ask the LangChain RAG endpoint
The project now ships with a small LangChain pipeline that wraps the same Chroma store and an Ollama chat model (default `CHAT_MODEL=llama3.1`).
Send a question with optional `k` for the number of context chunks:
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the dataset about?","k":4}' \
  http://localhost:8000/rag
```
On Windows `cmd.exe`, avoid the Unix-style backslashes and send it as a single
line instead:
```bat
curl -X POST -H "Content-Type: application/json" -d '{"query":"What is the dataset about?","k":4}' http://localhost:8000/rag
```
The response includes a generated answer plus the retrieved chunks and metadata for citations.

### 7) Chat UI
Open Open WebUI at:
- http://localhost:3000

Use it to chat with the local model (Ollama). You can extend it to call the `/rag` endpoint for retrieval-augmented responses.

### One-command helper script
To automate steps 1–4 and run a sample query, use:
```bash
bash run_local.sh
```
If you cloned on Windows, ensure the script has LF endings (e.g., `dos2unix run_local.sh`) before running to avoid `$'\r'` errors.
Environment variables `SOURCE_NAME`, `SINCE`, `UNTIL`, `LIMIT`, and `QUERY` let you override defaults.

### Tests
Install dev dependencies and run the test suite:
```bash
pip install -r requirements-dev.txt
pytest
```

## Notes on licensing & full text
This demo downloads files **only when**:
- fulltext.enabled = true
- the file URL domain is allowlisted in `sources.yaml`

You should only point this at content you are allowed to download and process.

## Configuration
Edit `sources.yaml`.

## Project structure
- `app/harvest/oai_pmh.py` – OAI-PMH harvesting
- `app/parse/*` – PDF/HTML parsing
- `app/index/*` – chunk, embed, store
- `app/api/main.py` – FastAPI LangChain RAG API
- `app/ingest.py` – CLI ingestion pipeline

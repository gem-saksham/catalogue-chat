#!/usr/bin/env bash

# Require bash so we avoid cryptic errors when the script is invoked via sh on
# systems where bash is not the default POSIX shell.
if [ -z "${BASH_VERSION:-}" ]; then
  echo "This script must be run with bash (e.g., 'bash run_local.sh')." >&2
  exit 1
fi

# Warn and exit early if the file was checked out with Windows-style newlines,
# which can produce `$'\r'` errors even under bash.
if grep -q $'\r' "$0"; then
  echo "Detected Windows-style line endings; please convert this script to LF (e.g., 'dos2unix run_local.sh')." >&2
  exit 1
fi

# Enable strict mode where supported; fall back gracefully when the shell
# lacks pipefail (e.g., when bash is configured without pipefail support).
set -eu
if ! set -o pipefail 2>/dev/null; then
  echo "Warning: shell does not support 'pipefail'; continuing without it." >&2
fi

# Quick-start helper for catalogue-chat.
# Requirements: Docker + docker-compose, curl, python, and jq available on PATH.

SOURCE_NAME=${SOURCE_NAME:-"Zenodo OAI demo"}
SINCE=${SINCE:-"2025-01-01"}
UNTIL=${UNTIL:-""}
LIMIT=${LIMIT:-50}
QUERY=${QUERY:-"graph neural networks"}

step() { echo -e "\n==> $1"; }

step "Checking Python version"
python scripts/check_python_version.py

step "Starting containers"
docker compose up -d

step "Pulling default Ollama models (llama3.1 + nomic-embed-text)"
docker exec $(docker ps -qf name=ollama) ollama pull llama3.1
docker exec $(docker ps -qf name=ollama) ollama pull nomic-embed-text

step "Running ingestion (source: ${SOURCE_NAME}, since: ${SINCE}, limit: ${LIMIT})"
python app/ingest.py --source "${SOURCE_NAME}" --since "${SINCE}" ${UNTIL:+--until "$UNTIL"} --limit "${LIMIT}"

step "Sample LangChain RAG question"
curl -X POST \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"${QUERY}\",\"k\":3}" \
  http://localhost:8000/rag | jq '.'

step "Done. Open Open WebUI at http://localhost:3000 to chat with your local model."

import argparse
import importlib.util
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# --- Imports Check (Leave as is) ---
REQUIRED_MODULES = {
    "yaml": "PyYAML",
    "requests": "requests",
    "tqdm": "tqdm",
    "sickle": "sickle",
    "lxml": "lxml",
    "bs4": "beautifulsoup4",
    "pypdf": "pypdf",
    "chromadb": "chromadb",
}

if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
    raise SystemExit(
        "This ingest script is tested with Python 3.10–3.12. "
        "Use a supported version or run inside Docker/WSL to avoid build failures."
    )

missing = [pkg for mod, pkg in REQUIRED_MODULES.items() if importlib.util.find_spec(mod) is None]
if missing:
    # FIX: Corrected missing parenthesis.
    joined = ", ".join(sorted(set(missing)))
    raise SystemExit(
        f"Missing dependencies detected ({joined}). Run `python -m pip install -r requirements.txt` first."
    )
# --- End Imports Check ---

import yaml
import requests
from tqdm import tqdm

from harvest.oai_pmh import harvest_records
from parse.pdf import extract_pdf_text
from parse.html import extract_html_text
from index.chunk import chunk_text
from index.embed import embed_texts
from index.store import get_collection


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def log_and_print(message: str, *args):
    text = message % args if args else message
    logger.info(text)
    print(text)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))  # when in docker
RAW_DIR = DATA_DIR / "raw"
PARSED_DIR = DATA_DIR / "parsed"
BATCH_SIZE = 32 # Define a batch size for upserts

def safe_filename(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s).strip("_")
    return s[:180] if s else "item"

def download_file(url: str, out_path: Path, max_mb: int = 80) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = 0
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_mb * 1024 * 1024:
                    log_and_print(f"File download exceeded max size of {max_mb}MB. Stopping download.")
                    return False
                f.write(chunk)
    return True

def try_get_zenodo_files(record_landing_url: str):
    """
    Zenodo OAI records often include an identifier/landing page URL.
    This helper scrapes the landing page for downloadable file links (best-effort).
    """
    try:
        # Increased timeout slightly
        html = requests.get(record_landing_url, timeout=45).text 
    except Exception as e:
        logger.warning(f"Failed to scrape Zenodo landing page {record_landing_url}: {e}")
        return []
    # Zenodo file download links often contain `/records/<id>/files/<name>?download=1`
    links = sorted(set(re.findall(r'https://zenodo\.org/records/\d+/files/[^"\s<>]+', html)))
    # Add download=1 if missing, to force download
    fixed = []
    for u in links:
        if "download=1" not in u:
            sep = "&" if "?" in u else "?"
            fixed.append(u + f"{sep}download=1")
        else:
            fixed.append(u)
    return fixed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="sources.yaml")
    parser.add_argument("--source", required=True, help="sources.yaml name")
    parser.add_argument("--since", default=None, help="YYYY-MM-DD (optional)")
    parser.add_argument("--until", default=None, help="YYYY-MM-DD (optional)")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    source = next((s for s in cfg["sources"] if s["name"] == args.source), None)
    if not source:
        raise SystemExit(f"Source not found: {args.source}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    coll = get_collection()

    since = args.since
    until = args.until

    log_and_print(
        "Starting harvest for source=%s since=%s until=%s limit=%s",
        args.source,
        since,
        until,
        args.limit,
    )

    records = harvest_records(
        base_url=source["endpoint"],
        metadata_prefix=source.get("metadata_prefix", "oai_dc"),
        set_spec=source.get("set"),
        since=since,
        until=until,
        limit=args.limit,
    )

    fulltext_cfg = source.get("fulltext", {}) or {}
    fulltext_enabled = bool(fulltext_cfg.get("enabled", False))
    allowed_domains = set(fulltext_cfg.get("allowed_domains", []))
    max_mb = int(fulltext_cfg.get("max_mb", 80))

    log_and_print("Harvested %s records. Fulltext enabled: %s", len(records), fulltext_enabled)
    
    # --- Batching Structures ---
    texts_to_embed = []
    metadatas_to_upsert = []
    ids_to_upsert = []
    # --- End Batching Structures ---

    total_chunks_ingested = 0

    for idx, rec in enumerate(tqdm(records, desc="Ingesting"), start=1):
        rec_id = rec.get("id") or rec.get("identifier") or rec.get("oai_identifier")
        if not rec_id:
             logger.warning(f"Record {idx} skipped: No valid ID found.")
             continue
             
        title = rec.get("title") or "Untitled"
        landing = rec.get("url") or rec.get("landing_url")

        logger.info(
            "[%s/%s] Ingesting record id=%s title=%r url=%s", idx, len(records), rec_id, title, landing
        )

        # Collect text sources: description + maybe fulltext
        texts = []
        meta_text = "\n".join(
            x for x in [
                f"Title: {title}",
                f"Creators: {rec.get('creators','')}",
                f"Subjects: {rec.get('subjects','')}",
                f"Description: {rec.get('description','')}",
                f"Published: {rec.get('date','')}",
                f"URL: {landing or ''}",
            ] if x
        ).strip()
        if meta_text:
            texts.append(("metadata", meta_text))

        downloaded_files = []
        if fulltext_enabled and landing and any(landing.startswith(f"https://{d}") for d in allowed_domains):
            for file_url in try_get_zenodo_files(landing):
                fname = safe_filename(file_url.split("/")[-1].split("?")[0])
                # Ensure the file path is unique and uses a safe ID
                out_path = RAW_DIR / safe_filename(rec_id) / fname 
                try:
                    ok = download_file(file_url, out_path, max_mb=max_mb)
                    if ok:
                        downloaded_files.append(out_path)
                    else:
                        logger.warning(f"Download failed or was too large for {file_url}")
                except Exception as e:
                    logger.error(f"Error downloading file {file_url}: {e}")
                    continue

        logger.info(
            "[%s/%s] Text sources before parsing: metadata=%s downloaded_files=%s",
            idx,
            len(records),
            bool(meta_text),
            len(downloaded_files),
        )

        # Parse downloaded files
        for fp in downloaded_files:
            try:
                if fp.suffix.lower() == ".pdf":
                    text = extract_pdf_text(fp)
                elif fp.suffix.lower() in (".html", ".htm"):
                    text = extract_html_text(fp.read_text(encoding="utf-8", errors="ignore"))
                else:
                    # best-effort plain text
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                if text and len(text.strip()) > 200:
                    texts.append((fp.name, text))
            except Exception as e:
                logger.error(f"Error parsing file {fp}: {e}")
                continue

        # Chunk + queue for embedding
        record_chunks = 0
        for label, t in texts:
            for i, chunk in enumerate(chunk_text(t)):
                doc_id = f"{rec_id}:{label}:{i}"
                meta = {
                    "record_id": rec_id,
                    "title": title,
                    "label": label,
                    "url": landing or "",
                    "chunk": i,
                }
                
                texts_to_embed.append(chunk)
                metadatas_to_upsert.append(meta)
                ids_to_upsert.append(doc_id)
                record_chunks += 1
                total_chunks_ingested += 1

                # If batch is full, process it
                if len(texts_to_embed) >= BATCH_SIZE:
                    log_and_print("Embedding and upserting batch of %s chunks...", len(texts_to_embed))
                    embeddings = embed_texts(texts_to_embed)
                    # NOTE: Chroma upsert is outside the tqdm loop to prevent locking the terminal
                    coll.upsert(
                        ids=ids_to_upsert,
                        documents=texts_to_embed,
                        embeddings=embeddings,
                        metadatas=metadatas_to_upsert,
                    )
                    # Reset batches
                    texts_to_embed = []
                    metadatas_to_upsert = []
                    ids_to_upsert = []
                    log_and_print("Batch upsert complete.")


        if texts:
            logger.info(
                "[%s/%s] Queued %s chunks from %s text source(s) for record id=%s",
                idx,
                len(records),
                record_chunks,
                len(texts),
                rec_id,
            )
        else:
            logger.info(
                "[%s/%s] No text extracted for record id=%s title=%r; skipped embedding",
                idx,
                len(records),
                rec_id,
                title,
            )
    
    # Process remaining batch (if any)
    if texts_to_embed:
        log_and_print("Processing final batch of %s chunks...", len(texts_to_embed))
        embeddings = embed_texts(texts_to_embed)
        coll.upsert(
            ids=ids_to_upsert,
            documents=texts_to_embed,
            embeddings=embeddings,
            metadatas=metadatas_to_upsert,
        )
        log_and_print("Final batch upsert complete.")

    log_and_print("Total chunks ingested: %s. Chroma count should reflect this number.", total_chunks_ingested)
    log_and_print("Done. You can now query the LangChain RAG endpoint at http://localhost:8000/rag")

if __name__ == "__main__":
    main()

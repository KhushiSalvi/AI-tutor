"""Fully automatic onboarding for a new book.

Drop a PDF into data/raw/, then run:
    python -m core.ingestion.auto_add

It will, with no further input:
  1. find any PDF in data/raw/ not already listed in sources.yaml
  2. guess a source id and a topic list from the book's own text
  3. append a new entry to sources.yaml
  4. chunk the new PDF (core.ingestion.ingest_pdf)
  5. embed only the new chunks into the vector index (core.retrieval.index --incremental)

Existing books and their embeddings are left untouched. Re-running with no new PDFs
does nothing and prints "Nothing to do."
"""
import re
import sys
from pathlib import Path

import pymupdf
import yaml

from core.ingestion.topics import guess_topics

SOURCES_FILE = Path("sources.yaml")
RAW_DIR = Path("data/raw")


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return re.sub(r"_+", "_", s) or "book"


def sample_text(pdf_path, pages=15):
    doc = pymupdf.open(pdf_path)
    try:
        n = len(doc)
        # sample from the middle of the book, front matter is rarely representative
        start = max(0, n // 4)
        return " ".join(doc[i].get_text() for i in range(start, min(start + pages, n)))
    finally:
        doc.close()


def load_sources():
    if not SOURCES_FILE.exists():
        return []
    with open(SOURCES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def save_sources(entries):
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(entries, f, sort_keys=False, allow_unicode=True)


def known_paths(entries):
    return {str(Path(e["path"])) for e in entries if e.get("type") == "pdf" and e.get("path")}


def unique_id(base, existing_ids):
    if base not in existing_ids:
        return base
    i = 2
    while f"{base}_{i}" in existing_ids:
        i += 1
    return f"{base}_{i}"


def main():
    entries = load_sources()
    known = known_paths(entries)
    existing_ids = {e["id"] for e in entries}

    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    new_pdfs = [p for p in pdfs if str(Path("data/raw") / p.name) not in known]

    if not new_pdfs:
        print("Nothing to do. Every PDF in data/raw/ is already in sources.yaml.")
        return []

    added_ids = []
    for pdf in new_pdfs:
        sid = unique_id(slugify(pdf.stem), existing_ids)
        existing_ids.add(sid)
        try:
            topics = guess_topics(sample_text(pdf))
        except Exception as e:
            print(f"  Could not read {pdf.name} to guess topics ({e}); tagging as 'general'.")
            topics = ["general"]
        entry = {
            "id": sid,
            "type": "pdf",
            "path": f"data/raw/{pdf.name}",
            "license": "personal copy, local use only (VERIFY before any public/shared use)",
            "topics": topics,
            "tier": "local",
        }
        entries.append(entry)
        added_ids.append(sid)
        print(f"+ {sid}\n    file: {pdf.name}\n    guessed topics: {topics}")

    save_sources(entries)
    print(f"\nsources.yaml updated with {len(added_ids)} new book(s).")
    print("Review the guessed topics above -- edit sources.yaml if any look wrong, then re-run to re-ingest.")
    return added_ids


if __name__ == "__main__":
    ids = main()
    if ids:
        print("\nNow ingesting and indexing the new book(s)...\n")
        import subprocess
        subprocess.run([sys.executable, "-m", "core.ingestion.ingest_pdf"], check=True)
        subprocess.run([sys.executable, "-m", "core.retrieval.index", "--incremental"], check=True)
        print("\nDone. The new book(s) are searchable now.")

"""Build/update the vector index.

Default (no flags): incremental. Skips any source_id whose chunks are already in the
index (tracked in data/index_state.json), so adding one new book only embeds that
book's chunks, not the whole corpus again.

--all: wipe and rebuild everything from data/processed/*.jsonl. Use this if you ever
change the embedding model, or if a source's chunk_ids changed shape (e.g. you edited
the chunking code) and old and new chunks might collide.

--incremental: explicit alias for the default, kept so scripts that call it by name
(auto_add.py) stay correct even if the default ever changes.
"""
import json
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

MODEL = "BAAI/bge-small-en-v1.5"
INDEX_DIR = "data/index"
STATE_FILE = Path("data/index_state.json")


def load_chunks():
    by_source = {}
    for f in Path("data/processed").glob("*.jsonl"):
        source_id = f.stem
        with open(f, encoding="utf-8") as fh:
            by_source[source_id] = [json.loads(line) for line in fh]
    return by_source


def load_state():
    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_state(indexed_sources):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(sorted(indexed_sources)), encoding="utf-8")


def embed_and_add(col, model, chunks, batch=64):
    for i in range(0, len(chunks), batch):
        piece = chunks[i:i + batch]
        emb = model.encode([c["text"] for c in piece], normalize_embeddings=True)
        col.upsert(
            ids=[c["chunk_id"] for c in piece],
            embeddings=emb.tolist(),
            documents=[c["text"] for c in piece],
            metadatas=[{
                "source_id": c["source_id"],
                "page": c["page"] or 0,
                "timestamp": c["timestamp"] or "",
                "topics": ",".join(c["topics"]),
                "tier": c["tier"],
            } for c in piece],
        )
        print(f"  {min(i + batch, len(chunks))}/{len(chunks)}")


def main():
    full_rebuild = "--all" in sys.argv
    by_source = load_chunks()
    client = chromadb.PersistentClient(path=INDEX_DIR)

    if full_rebuild:
        try:
            client.delete_collection("ee_chunks")
        except Exception:
            pass
        col = client.create_collection("ee_chunks", metadata={"hnsw:space": "cosine"})
        to_process = dict(by_source)
        print(f"Full rebuild: {len(to_process)} source(s), "
              f"{sum(len(v) for v in to_process.values())} chunks.")
    else:
        col = client.get_or_create_collection("ee_chunks", metadata={"hnsw:space": "cosine"})
        done = load_state()
        to_process = {sid: chunks for sid, chunks in by_source.items() if sid not in done}
        if not to_process:
            print("Nothing new to index. Every processed source is already embedded.")
            print("Use --all to force a full rebuild (e.g. after changing the embedding model).")
            return
        print(f"Incremental: {len(to_process)} new source(s), "
              f"{sum(len(v) for v in to_process.values())} chunks.")

    model = SentenceTransformer(MODEL)
    for sid, chunks in to_process.items():
        print(f"Embedding {sid} ({len(chunks)} chunks)...")
        embed_and_add(col, model, chunks)

    state = set(by_source) if full_rebuild else (load_state() | set(to_process))
    save_state(state)
    print("Done.")


if __name__ == "__main__":
    main()

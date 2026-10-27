import sys

import chromadb
from sentence_transformers import SentenceTransformer

sys.stdout.reconfigure(encoding="utf-8")

MODEL = "BAAI/bge-small-en-v1.5"
PREFIX = "Represent this sentence for searching relevant passages: "


def search(query, k=5):
    model = SentenceTransformer(MODEL)
    col = chromadb.PersistentClient(path="data/index").get_collection("ee_chunks")
    q = model.encode([PREFIX + query], normalize_embeddings=True)
    res = col.query(query_embeddings=q.tolist(), n_results=k)
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        print(f"\n[{meta['source_id']} | page {meta['page']} | score {1 - dist:.2f}]")
        print(doc[:400] + "...")


if __name__ == "__main__":
    search(" ".join(sys.argv[1:]))

import json
import re
import sys
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

sys.stdout.reconfigure(encoding="utf-8")

EMB = "BAAI/bge-small-en-v1.5"
RERANK = "cross-encoder/ms-marco-MiniLM-L-6-v2"
PREFIX = "Represent this sentence for searching relevant passages: "


def tok(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class Retriever:
    def __init__(self):
        self.chunks = []
        for f in Path("data/processed").glob("*.jsonl"):
            with open(f, encoding="utf-8") as fh:
                self.chunks += [json.loads(line) for line in fh]
        self.by_id = {c["chunk_id"]: c for c in self.chunks}
        self.bm25 = BM25Okapi([tok(c["text"]) for c in self.chunks])
        self.emb = SentenceTransformer(EMB)
        self.col = chromadb.PersistentClient(path="data/index").get_collection("ee_chunks")
        self.reranker = CrossEncoder(RERANK)

    def dense(self, q, n):
        v = self.emb.encode([PREFIX + q], normalize_embeddings=True)
        return self.col.query(query_embeddings=v.tolist(), n_results=n)["ids"][0]

    def sparse(self, q, n):
        scores = self.bm25.get_scores(tok(q))
        top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
        return [self.chunks[i]["chunk_id"] for i in top]

    def search(self, q, k=5, pool=30, mode="rerank", max_page=None, min_page=None):
        # mode: "dense" | "hybrid" | "rerank"
        if mode == "dense":
            return [(self.by_id[c], None) for c in self.dense(q, k)]
        fused = {}
        for ranked in (self.dense(q, pool), self.sparse(q, pool)):
            for rank, cid in enumerate(ranked):
                fused[cid] = fused.get(cid, 0) + 1 / (60 + rank)  # reciprocal rank fusion
        cand = sorted(fused, key=fused.get, reverse=True)
        if max_page is not None:
            cand = [c for c in cand if self.by_id[c]["page"] <= max_page]
        if min_page is not None:
            cand = [c for c in cand if self.by_id[c]["page"] >= min_page]
        cand = cand[:20]
        if mode == "hybrid":
            return [(self.by_id[c], fused[c]) for c in cand[:k]]
        scores = self.reranker.predict([(q, self.by_id[c]["text"]) for c in cand])
        pairs = sorted(zip(cand, scores), key=lambda p: p[1], reverse=True)
        return [(self.by_id[c], float(s)) for c, s in pairs[:k]]


if __name__ == "__main__":
    mode = "rerank"
    args = sys.argv[1:]
    if args and args[0] in ("dense", "hybrid", "rerank"):
        mode, args = args[0], args[1:]
    r = Retriever()
    for chunk, score in r.search(" ".join(args), mode=mode):
        s = f"{score:.2f}" if score is not None else "-"
        print(f"\n[{chunk['source_id']} | page {chunk['page']} | score {s}]")
        print(chunk["text"][:400] + "...")

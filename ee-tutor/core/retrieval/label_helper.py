import sys

from core.retrieval.hybrid import Retriever

sys.stdout.reconfigure(encoding="utf-8")

r = Retriever()
qs = [l.strip() for l in open("eval/questions.txt", encoding="utf-8-sig") if l.strip()]
for q in qs:
    print("\n" + "=" * 80 + "\nQ:", q)
    seen = {}
    for mode in ("dense", "hybrid", "rerank"):
        for c, _ in r.search(q, k=5, mode=mode):
            seen.setdefault(c["chunk_id"], c)
    for c in sorted(seen.values(), key=lambda c: c["page"]):
        print(f"  p{c['page']}: {c['text'][:150].replace(chr(10), ' ')}...")

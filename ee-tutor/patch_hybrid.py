p = "core/retrieval/hybrid.py"
s = open(p, encoding="utf-8-sig").read()

old_sig = 'def search(self, q, k=5, pool=30, mode="rerank"):'
new_sig = 'def search(self, q, k=5, pool=30, mode="rerank", max_page=None):'
old_cand = '        cand = sorted(fused, key=fused.get, reverse=True)[:20]'
new_cand = (
    '        cand = sorted(fused, key=fused.get, reverse=True)\n'
    '        if max_page is not None:\n'
    '            cand = [c for c in cand if self.by_id[c]["page"] <= max_page]\n'
    '        cand = cand[:20]'
)

assert old_sig in s and old_cand in s, "pattern not found, paste your search() function here"
s = s.replace(old_sig, new_sig).replace(old_cand, new_cand)
open(p, "w", encoding="utf-8").write(s)
print("patched OK")

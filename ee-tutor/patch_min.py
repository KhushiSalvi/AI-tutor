p = "core/retrieval/hybrid.py"
s = open(p, encoding="utf-8-sig").read()
old_sig = 'mode="rerank", max_page=None):'
new_sig = 'mode="rerank", max_page=None, min_page=None):'
old_f = '            cand = [c for c in cand if self.by_id[c]["page"] <= max_page]'
new_f = old_f + '\n        if min_page is not None:\n            cand = [c for c in cand if self.by_id[c]["page"] >= min_page]'
assert old_sig in s and old_f in s, "pattern not found, paste your search() function"
s = s.replace(old_sig, new_sig).replace(old_f, new_f)
open(p, "w", encoding="utf-8").write(s)
print("patched OK")

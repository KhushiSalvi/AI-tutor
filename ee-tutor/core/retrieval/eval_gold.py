import json
import sys

from core.retrieval.hybrid import Retriever

sys.stdout.reconfigure(encoding="utf-8")

MAX_BASIC_PAGE = 470  # set from the table of contents

gold = json.load(open("eval/gold.json", encoding="utf-8-sig"))
r = Retriever()


def first_hit(top, ranges):
    for i, (c, _) in enumerate(top, 1):
        if any(lo <= c["page"] <= hi for lo, hi in ranges):
            return i
    return None


configs = [
    ("dense", "dense", False),
    ("hybrid", "hybrid", False),
    ("rerank", "rerank", False),
    ("hybrid+filter", "hybrid", True),
    ("rerank+filter", "rerank", True),
]

for name, mode, filt in configs:
    hit3, rr = 0, 0.0
    print(f"\n===== {name} =====")
    for g in gold:
        mp = MAX_BASIC_PAGE if (filt and g.get("level") == "basic" and mode != "dense") else None
        top = r.search(g["q"], k=5, mode=mode, **({"max_page": mp} if mp else {}))
        rank = first_hit(top, g["pages"])
        adv = first_hit(top, g.get("advanced_pages", []))
        if rank and rank <= 3:
            status = "OK      "
        elif adv and adv <= 3:
            status = "TOO-ADV "
        else:
            status = "MISS    "
        hit3 += status.startswith("OK")
        rr += 1 / rank if rank else 0
        print(f"{status} rank={rank}  {g['q']}")
    n = len(gold)
    print(f"--> {name}: hit@3 {hit3}/{n}   MRR {rr/n:.2f}")

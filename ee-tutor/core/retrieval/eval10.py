import sys

from core.retrieval.hybrid import Retriever

sys.stdout.reconfigure(encoding="utf-8")

# (question, keywords: at least one should appear in a relevant chunk)
QS = [
    ("what is threshold voltage of a MOSFET", ["threshold voltage", "vth"]),
    ("how does a MOSFET work in saturation region", ["saturation", "pinch"]),
    ("channel length modulation", ["channel length modulation", "lambda", "λ"]),
    ("body effect", ["body effect", "substrate bias"]),
    ("small signal model of MOSFET", ["small-signal", "small signal", "gm"]),
    ("triode region current equation", ["triode", "linear region", "deep triode"]),
    ("transconductance of a MOSFET", ["transconductance", "gm"]),
    ("what is overdrive voltage", ["overdrive"]),
    ("MOSFET as a switch", ["switch"]),
    ("output resistance of a MOSFET", ["output resistance", "ro"]),
]

r = Retriever()
for mode in ("dense", "rerank"):
    hits = 0
    print(f"\n===== {mode} =====")
    for q, kws in QS:
        top = r.search(q, k=3, mode=mode)
        ok = any(any(k in c["text"].lower() for k in kws) for c, _ in top)
        hits += ok
        pages = [c["page"] for c, _ in top]
        print(f"{'OK ' if ok else 'MISS'} {q}  pages={pages}")
    print(f"--> {mode}: {hits}/{len(QS)}")

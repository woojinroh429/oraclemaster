"""Generate the report's results tables straight from the run logs.

Forty instances times four numbers is a hundred and sixty transcriptions, and a report is exactly
the document where one silently wrong digit is worst.  So nothing here is typed by hand: the
tables are read out of results/train/*.log and results/fx_*.log, which are the same files the
harnesses wrote and committed.

Prints LaTeX ready to paste, and a plain summary to read.

Run: python3.12 harness/mktable.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINE = re.compile(r"^P(\d+)\s+\S.*?obj=(\d+)\s+Z1=([\d.]+)\s+Z2=(\S+)\s+Z3=([\d.]+)\s+feas=(\S+)")


def read(path):
    if not os.path.exists(path):
        return None
    for ln in reversed(open(path).read().splitlines()):
        m = LINE.match(ln.strip())
        if m:
            return dict(p=int(m.group(1)), obj=int(m.group(2)), z1=float(m.group(3)),
                        z2=m.group(4), z3=float(m.group(5)), feas=m.group(6))
    return None


def meta(p, sub="train"):
    f = os.path.join(HERE, "data", sub, "prob_%d.json" % p)
    if not os.path.exists(f):
        return None
    j = json.load(open(f))
    return len(j["blocks"]), len(j["bays"])


rows = []
for p in range(1, 41):
    r = read(os.path.join(HERE, "results/train/t%d.log" % p))
    m = meta(p)
    if r and m:
        r["n"], r["m"] = m
        rows.append(r)

if not rows:
    print("no training logs yet")
    sys.exit(0)

print("%% %d of 40 training instances, 60 s each" % len(rows))


def fmt(v):
    s = "%d" % int(round(float(v)))
    out, c = "", 0
    for ch in reversed(s):
        if c and c % 3 == 0:
            out = r"\," + out
        out = ch + out
        c += 1
    return out


# SIDE BY SIDE.  Forty rows stacked vertically fill a whole page, which pushed every float in
# the document to the end and left the tables nowhere near the text that discusses them.  Two
# blocks of twenty halve the height and read better besides.
half = (len(rows) + 1) // 2
left, right = rows[:half], rows[half:]
cell = lambda r: (r"%d & %d & %d & %s & %s & %s & %s"
                  % (r["p"], r["n"], r["m"], fmt(r["z1"]), fmt(r["z2"]), fmt(r["z3"]),
                     fmt(r["obj"])))
head = r"Inst. & $n$ & $m$ & $Z_1$ & $Z_2$ & $Z_3$ & Obj."
print(r"\begin{tabular}{rrrrrrr@{\qquad}rrrrrrr}")
print(r"\toprule")
print(head + " & " + head + r" \\")
print(r"\midrule")
for i in range(half):
    a = cell(left[i])
    b = cell(right[i]) if i < len(right) else " & " * 6
    print(a + " & " + b + r" \\")
print(r"\bottomrule")
print(r"\end{tabular}")

bad = [r["p"] for r in rows if r["feas"] != "y"]
print("\n%% feasible: %d of %d%s" % (len(rows) - len(bad), len(rows),
                                     ("  INFEASIBLE: " + str(bad)) if bad else ""))
z1z = [r["p"] for r in rows if r["z1"] == 0]
print("%% Z1 == 0 on %d of %d instances: %s" % (len(z1z), len(rows), z1z))

# The claim the report makes about instance structure has to come from the data, not from memory.
print("\n--- summary ---")
print("instances solved      : %d of 40" % len(rows))
print("feasible              : %d" % (len(rows) - len(bad)))
print("Z1 = 0                : %d" % len(z1z))
print("objective range       : %d .. %d" % (min(r["obj"] for r in rows),
                                            max(r["obj"] for r in rows)))

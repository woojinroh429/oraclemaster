"""The two training sets side by side, in aggregate.

The report shows the preliminary set instance by instance because it is what the earlier rounds
were tuned against, and there is no room for a second forty-row table inside ten pages -- measured,
it costs a page, and no layout recovers it.  What the reader actually needs from the final-round
set is not its individual cells but how its shape differs, and that is a small table.

The contrast is the point and it is stark: the preliminary set has $Z_1 = 0$ on exactly half its
instances, the final set on none of them.  A report that showed only the first would be describing
a problem the final round does not pose.

Reads the same logs as mktable.py, so nothing is retyped here either.

Run: python3.12 harness/mksummary.py
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
                        z2=float(m.group(4)), z3=float(m.group(5)), feas=m.group(6))
    return None


def load(logdir, prefix, dataset):
    rows = []
    for p in range(1, 41):
        r = read(os.path.join(HERE, logdir, "%s%d.log" % (prefix, p)))
        f = os.path.join(HERE, "data", dataset, "prob_%d.json" % p)
        if r and os.path.exists(f):
            j = json.load(open(f))
            r["n"], r["m"] = len(j["blocks"]), len(j["bays"])
            r["w"] = j["weights"]
            rows.append(r)
    return rows


def fmt(v):
    s = "%d" % int(round(float(v)))
    out, c = "", 0
    for ch in reversed(s):
        if c and c % 3 == 0:
            out = "{,}" + out
        out = ch + out
        c += 1
    return out


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def rng(rows, key):
    xs = [r[key] for r in rows]
    return "%s & %s--%s" % (fmt(med(xs)), fmt(min(xs)), fmt(max(xs)))


A = load("results/train", "t", "train")
B = load("results/stage2", "f", "stage2")
if not A or not B:
    sys.exit("missing logs: preliminary %d, final %d" % (len(A), len(B)))

print(r"\begin{tabular}{lrrrr}")
print(r"\toprule")
print(r" & \multicolumn{2}{c}{Preliminary} & \multicolumn{2}{c}{Final} \\")
print(r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}")
print(r" & median & range & median & range \\")
print(r"\midrule")
print(r"Blocks $n$ & %s & %s \\" % (rng(A, "n"), rng(B, "n")))
print(r"Bays $m$ & %s & %s \\" % (rng(A, "m"), rng(B, "m")))
print(r"Tardiness $Z_1$ & %s & %s \\" % (rng(A, "z1"), rng(B, "z1")))
print(r"Imbalance $Z_2$ & %s & %s \\" % (rng(A, "z2"), rng(B, "z2")))
print(r"Preference $Z_3$ & %s & %s \\" % (rng(A, "z3"), rng(B, "z3")))
print(r"Objective & %s & %s \\" % (rng(A, "obj"), rng(B, "obj")))
print(r"\midrule")
print(r"Instances with $Z_1=0$ & \multicolumn{2}{c}{%d of %d} & \multicolumn{2}{c}{%d of %d} \\"
      % (sum(1 for r in A if r["z1"] == 0), len(A),
         sum(1 for r in B if r["z1"] == 0), len(B)))
print(r"Feasible & \multicolumn{2}{c}{%d of %d} & \multicolumn{2}{c}{%d of %d} \\"
      % (sum(1 for r in A if r["feas"] == "y"), len(A),
         sum(1 for r in B if r["feas"] == "y"), len(B)))
print(r"\bottomrule")
print(r"\end{tabular}")

print("\n--- summary ---")
for name, rows in (("preliminary", A), ("final", B)):
    print("%-12s %2d instances, %2d feasible, Z1=0 on %2d, obj %s..%s"
          % (name, len(rows), sum(1 for r in rows if r["feas"] == "y"),
             sum(1 for r in rows if r["z1"] == 0),
             fmt(min(r["obj"] for r in rows)), fmt(max(r["obj"] for r in rows))))

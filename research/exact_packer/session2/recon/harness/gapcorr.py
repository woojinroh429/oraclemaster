"""Does the gap signal predict whether more rounds pay?

The adaptive design being considered -- cut round 1 short when the minimum rests on a single
worker, leave it alone when several workers sit near the minimum -- is only worth building if the
signal it keys on actually predicts the outcome.  Otherwise it is a hard-coded knob wearing a
measurement as a disguise, which is the thing this codebase refuses to ship.

Per (instance, replicate) it pairs:

    gap   from the R=1 run's own WSTAT line: (second_best - best) / best among that round's
          workers.  Large means the answer rests on one draw.
    gain  the improvement more rounds actually delivered: (obj_R1 - min(obj_R2, obj_R3)) / obj_R1,
          positive when rounds helped.

and reports Spearman rank correlation, because the relationship only needs to be monotone for a
threshold rule to work and rank correlation is not moved by the one instance with a huge swing.

A rule needs the sign to be right AND the separation to be visible.  The printout therefore also
splits the pairs at the median gap and shows the mean gain on each side: that difference is what
a threshold rule would actually capture, and if it is near zero the rule buys nothing however
good the correlation looks.

    usage: python3.12 harness/gapcorr.py [results/audit/rounds.log]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/rounds.log")

TAG = re.compile(r"^#\s*\[r(\d+)\.R(\d+)\.(\d+)\]")
OBJ = re.compile(r"^P\d+\s+\[r(\d+)\.R(\d+)\.(\d+)\].*?obj=(\d+)")
WST = re.compile(r"^WSTAT round=\d+ n=\d+\s+(.*?)\s+spread=")

obj, gap, cur = {}, {}, None
for ln in open(LOG, errors="replace"):
    ln = ln.strip()
    m = TAG.match(ln)
    if m:
        cur = (int(m.group(1)), int(m.group(2)), int(m.group(3)))   # rep, R, prob
        continue
    m = WST.match(ln)
    if m and cur and cur[1] == 1 and cur not in gap:      # round 0 of the R=1 arm only
        v = sorted(float(x) for x in m.group(1).split() if x != "-")
        if len(v) >= 2 and v[0] > 0:
            gap[cur] = 100.0 * (v[1] - v[0]) / v[0]
        continue
    m = OBJ.match(ln)
    if m:
        obj[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = int(m.group(4))

pairs = []
for (rep, R, p) in list(obj):
    if R != 1:
        continue
    o1 = obj[(rep, 1, p)]
    more = [obj[k] for k in ((rep, 2, p), (rep, 3, p)) if k in obj]
    g = gap.get((rep, 1, p))
    if not more or g is None or o1 <= 0:
        continue
    pairs.append((g, 100.0 * (o1 - min(more)) / o1, p, rep))

if len(pairs) < 4:
    sys.exit("only %d complete (gap, gain) pairs -- let rounds run further" % len(pairs))


def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = 0.5 * (i + j) + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((x - mb) ** 2 for x in b) ** 0.5
    if va == 0 or vb == 0:
        return float("nan")
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb)


pairs.sort()
print("%-6s %-4s %9s %9s   %s" % ("inst", "rep", "gap", "gain", ""))
for g, gain, p, rep in pairs:
    print("P%-5d %-4d %8.2f%% %8.2f%%   %s" % (p, rep, g, gain,
                                               "rounds paid" if gain > 0 else ""))

gs = [x[0] for x in pairs]
gn = [x[1] for x in pairs]
rho = pearson(rank(gs), rank(gn))
print("\n%d pairs, Spearman rho = %+.3f" % (len(pairs), rho))

mid = sorted(gs)[len(gs) // 2]
lo = [x[1] for x in pairs if x[0] < mid]
hi = [x[1] for x in pairs if x[0] >= mid]
if lo and hi:
    print("split at gap %.2f%%:  low-gap mean gain %+.2f%% (n=%d),"
          "  high-gap mean gain %+.2f%% (n=%d)"
          % (mid, sum(lo) / len(lo), len(lo), sum(hi) / len(hi), len(hi)))
    print("separation %+.2f%% -- this is what a threshold rule would capture"
          % (sum(hi) / len(hi) - sum(lo) / len(lo)))

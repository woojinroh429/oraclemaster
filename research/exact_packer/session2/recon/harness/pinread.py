"""Run-to-run variance of one configuration, which is the variance that reaches the score.

Worker spread cannot answer this: it is (max-min)/min and the answer is min, so it moves with
quality by construction.  This repeats the identical configuration and measures how far the FINAL
objectives fall from each other.

    usage: python3.12 harness/pinread.py [logfile]
"""
import os, re, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/pin.log")
ROW = re.compile(r"^P(\d+)\s+\[r\d+\.(\w+)\.(\d+)\]\s+\d+s\s+obj=(\d+)")

d = defaultdict(list)
for ln in open(LOG, errors="replace"):
    m = ROW.match(ln)
    if m and int(m.group(1)) == int(m.group(3)):
        d[(int(m.group(3)), m.group(2))].append(int(m.group(4)))

probs = sorted({p for p, _ in d})
arms = []
for _, a in d:
    if a not in arms: arms.append(a)
print("%-5s %-7s %3s %13s %13s %9s   %s" % ("inst", "arm", "n", "best", "median", "spread", "runs"))
agg = defaultdict(list)
for p in probs:
    for a in arms:
        v = d.get((p, a))
        if not v: continue
        sp = 100.0 * (max(v) - min(v)) / min(v)
        if len(v) > 1: agg[a].append(sp)
        print("P%-4d %-7s %3d %13d %13.0f %8.2f%%   %s"
              % (p, a, len(v), min(v), statistics.median(v), sp, " ".join(str(x) for x in v)))
    print()
for a in arms:
    if agg[a]:
        print("%-7s run-to-run spread over %d instances: median %.2f%%  (%s)"
              % (a, len(agg[a]), statistics.median(agg[a]),
                 " ".join("%.1f%%" % x for x in agg[a])))
print("\nFewer than 3 repeats per cell makes the spread an underestimate; it can only grow.")

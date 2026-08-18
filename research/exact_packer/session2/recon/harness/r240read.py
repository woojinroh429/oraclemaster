"""Read r240 the way the competition scores it: by the draw you actually submit.

The mean is the wrong statistic here and it has misled this project before.  A submission is ONE
run.  If an arm returns 3.28M twice and 3.81M once, its average looks fine and one submission in
three is 16% down -- which is what the three submitted score sets show, every per-instance move
between them smaller than the algorithm's own spread.

So this ranks on the WORST draw, reports the spread beside it, and says plainly when the arms
cannot be separated.  OGC_ROUNDS is meant to remove the bad draw, not to raise the average: R=2
runs two half-length searches and keeps the better, so a bad outcome needs both halves to land
badly.  If it works, the worst draw improves while the median may not move at all -- and an arm
whose median is unchanged and whose worst case narrows is a win by this measure.

Also prints, per instance, how each arm's draws are distributed, because "tight with an occasional
outlier" and "uniformly wide" call for different remedies and the summary statistics hide the
difference.

    usage: python3.12 harness/r240read.py [logfile]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/r240.log")
OBJ = re.compile(r"^P\d+\s+\[r(\d+)\.R(\d+)\.(\d+)\].*?obj=(\d+)")

d = {}
for ln in open(LOG, errors="replace"):
    m = OBJ.match(ln.strip())
    if m:
        d.setdefault((int(m.group(3)), int(m.group(2))), []).append(int(m.group(4)))

if not d:
    sys.exit("no runs yet")


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


probs = sorted({p for p, _ in d})
Rs = sorted({r for _, r in d})

print("%-6s %-3s %-4s %12s %12s %12s %8s   draws" % ("inst", "R", "n", "best", "median", "WORST", "spread"))
wins = {r: 0 for r in Rs}
for p in probs:
    for R in Rs:
        v = d.get((p, R))
        if not v:
            continue
        print("P%-5d %-3d %-4d %12d %12.0f %12d %7.2f%%   %s"
              % (p, R, len(v), min(v), med(v), max(v),
                 100.0 * (max(v) - min(v)) / min(v), " ".join("%d" % x for x in v)))
    full = {R: d[(p, R)] for R in Rs if (p, R) in d and len(d[(p, R)]) == len(d.get((p, Rs[0]), []))}
    if len(full) == len(Rs) and full:
        b = min(full, key=lambda R: max(full[R]))       # ranked on the worst draw
        wins[b] += 1
        print("      -> best worst-case: R=%d\n" % b)
    else:
        print()

if any(wins.values()):
    print("worst-case winner count: %s" % {("R%d" % r): n for r, n in wins.items()})
    print("\nRanked on the worst draw, not the mean: a submission is one run, and an arm whose")
    print("median is unchanged while its worst case narrows is the win being looked for.")

"""P3's score is min-of-4.  Is four long attempts the right way to spend brk's time?

WHAT THE SIX-WAY LOG SHOWED.  In a 240 s P3 run brk produced exactly four solutions --
94,375 / 86,975 / 91,590 / 100,740 -- and the reported score, 86,975, is their MINIMUM.  So the
instance's objective is a best-of-4 draw from a distribution spanning 13,765, and the
80,795-90,225 spread everyone has been reading as instability is that order statistic.  Nothing
about making the code faster removes it.

WHY THAT IS A LEVER RATHER THAN A COMPLAINT.  Under min-of-N, halving each attempt to double N is
a good trade whenever per-attempt quality degrades more slowly than the extra draw improves the
minimum.  That is an empirical question about ONE curve -- objective against ask -- and this
measures it instead of arguing it.

METHOD.  Call repack directly on a fixed incumbent at several asks, many seeds each (repack
rotates its own seed per call, so repeats in one process are independent draws).  Then, for a
FIXED total time T, bootstrap the minimum of T/ask draws at each ask.  The comparison is
therefore at equal spend, which is the only comparison that decides anything: 4 x 40 s against
8 x 20 s against 16 x 10 s.

WHAT WOULD MAKE THIS A GATE, AND WHY IT IS NOT.  The output is a curve, not a P3 constant.  If
short asks win, the change is to how the scheduler splits brk's total time -- one policy, every
instance.  If long asks win, the current split is already right and the min-of-N framing is
answered rather than acted on.  Either way P6 and P4 get measured on the same curve before
anything moves.

Run: python3.12 harness/minofn.py <prob> <reps> <asks...>
  e.g. python3.12 harness/minofn.py 3 12 10 20 40 80
"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 12
ASKS = [float(a) for a in sys.argv[3:]] or [10.0, 20.0, 40.0, 80.0]
os.environ["WORKERS"] = "1"

import bayrepack as R                                   # noqa: E402
import myalgorithm as A                                 # noqa: E402
import utils                                            # noqa: E402

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
INC = os.path.join(HERE, "results/p%d_incumbent.json" % PROB)
if not os.path.exists(INC):
    print("no incumbent for P%d" % PROB)
    raise SystemExit(1)
sol = json.load(open(INC))
sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
base = A._total(d, sol, None)[0]
print("P%d incumbent objective %.0f, %d reps per ask" % (PROB, base, REPS))
print("  %-8s %8s %10s %10s %10s %10s" % ("ask", "solved", "best", "median", "worst", "sec/call"))

samples = {}
for ask in ASKS:
    got, el0 = [], time.time()
    for _ in range(REPS):
        s = R.repack(d, sol, ask, A._total, A._build_operations, A._ogc_fast_engine, hard=1e9)
        if s is None:
            continue
        cand = dict(sol)
        cand["operations"] = s
        o = A._total(d, cand, None)[0]
        if o < float("inf"):
            got.append(o)
    per = (time.time() - el0) / max(1, REPS)
    samples[ask] = got
    if got:
        g = sorted(got)
        print("  %-8.0f %8d %10.0f %10.0f %10.0f %10.1f"
              % (ask, len(got), g[0], g[len(g) // 2], g[-1], per))
    else:
        print("  %-8.0f %8d %10s %10s %10s %10.1f" % (ask, 0, "-", "-", "-", per))

# EQUAL SPEND.  A best-of-N at one ask is only comparable to another if both are given the same
# seconds, so N is derived from the budget rather than fixed.
T = max(ASKS) * 4.0
print("\n  at a fixed %.0f s of brk time, expected best-of-N (2000 bootstrap draws):" % T)
print("  %-8s %6s %12s %12s" % ("ask", "N", "expected min", "10th pct"))
rnd = random.Random(20260802)
for ask in ASKS:
    g = samples[ask]
    if not g:
        continue
    n = max(1, int(T / ask))
    mins = sorted(min(rnd.choice(g) for _ in range(n)) for _ in range(2000))
    print("  %-8.0f %6d %12.0f %12.0f" % (ask, n, sum(mins) / len(mins), mins[len(mins) // 10]))

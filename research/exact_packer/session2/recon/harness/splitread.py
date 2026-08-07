"""Read the work-budget split: does the same total work buy more as one wide draw or n narrow ones?

    usage: python3.12 harness/splitread.py results/audit/split.log

Reports, per instance and per split n:

    best     min over the n draws -- what a worker would return, and what scoring pays for
    median   the middle draw, which says whether the search itself moved or only the luck did
    secs     total wall time for the n draws.  EQUAL WORK IS NOT EQUAL TIME: every draw re-enters
             the engine and rebuilds occupancy, so this is the tax a split pays and it decides
             whether a work-space win survives into a 240 s budget.

There is no noise term: every cell is work-budgeted, and three repeats of one configuration
returned an identical objective AND an identical placement digest.  A difference here is real, and
its size is its size.
"""
import re, sys, statistics
from collections import defaultdict

LOG = sys.argv[1] if len(sys.argv) > 1 else "results/audit/split.log"
ROW = re.compile(r"^P(\d+)\s+\[p(\d+)\.n(\d+)\.d(\d+)\]\s+work=(\d+)\s+.*obj=(\d+|inf)\s+"
                 r"feas=(\w)\s+([\d.]+)s\s+digest=(\S+)")

cells = defaultdict(list)          # (prob, n) -> [(obj, secs, digest, feas)]
for ln in open(LOG, errors="replace"):
    m = ROW.match(ln)
    if not m:
        continue
    p, n = int(m.group(2)), int(m.group(3))
    obj = float("inf") if m.group(6) == "inf" else int(m.group(6))
    cells[(p, n)].append((obj, float(m.group(8)), m.group(9), m.group(7)))

if not cells:
    print("no split cells in", LOG); sys.exit(0)

probs = sorted({p for p, _ in cells})
for p in probs:
    ns = sorted(n for pp, n in cells if pp == p)
    base = None
    print("=" * 74)
    print("P%-3d   W=24000 total work per arm" % p)
    print("  %-4s %-6s %12s %12s %8s %9s %8s" %
          ("n", "work/d", "best", "median", "secs", "vs n=1", "infeas"))
    for n in ns:
        v = cells[(p, n)]
        got = len(v)
        objs = [o for o, _, _, _ in v if o < float("inf")]
        secs = sum(s for _, s, _, _ in v)
        bad = sum(1 for _, _, _, f in v if f != "y")
        if not objs:
            print("  %-4d %-6s %12s (%d draws, all infeasible)" % (n, 24000 // n, "-", got))
            continue
        b = min(objs)
        if n == 1:
            base = b
        rel = ("%+.2f%%" % (100.0 * (b - base) / base)) if base else "-"
        star = "" if got == n else "  <- %d/%d draws present" % (got, n)
        print("  %-4d %-6d %12d %12d %7.1fs %9s %8d%s" %
              (n, 24000 // n, b, int(statistics.median(objs)), secs, rel, bad, star))
    # a split that wins on work but costs seconds has to be judged on seconds too
    if base:
        t1 = sum(s for _, s, _, _ in cells[(p, 1)])
        for n in ns:
            if n == 1:
                continue
            tn = sum(s for _, s, _, _ in cells[(p, n)])
            print("     n=%-3d wall-time tax vs n=1: %+.1f%%" % (n, 100.0 * (tn - t1) / t1))
print()
print("A split that improves `best` but not `median` bought luck, not search -- the same test used")
print("on the workers.  A split that improves both but costs >20% wall time may still lose at 240 s.")

"""What shape is the worker distribution, and how much is the minimum actually buying?

The variance picture so far has two numbers that do not obviously fit together: the four workers
of a single run land a median of 29% apart, yet the run's answer -- the minimum over them -- moves
only a few percent between runs.  The minimum is absorbing the spread.  Where it fails to, the
score takes the hit, and P1 and P6 are where it failed.

Whether more draws (OGC_ROUNDS) can help depends on the SHAPE of that distribution, not its width:

  gain    (median_worker - min_worker) / min_worker, per run.  How much the min is already
          winning over a typical worker.  A large gain means the left tail is where the value is
          and sampling it more often is worth something.

  gap     (second_min - min) / min.  If the best worker is far below the second best, the answer
          rests on ONE draw and is fragile -- lose that worker and the run is much worse.  If the
          top two are close, the min is robust and extra draws buy less.

  span    (max - min) / min, the raw spread, for reference.

Reads any log with WSTAT lines: abvar, samebuild, rounds, wspread.  Costs nothing to run.

    usage: python3.12 harness/wshape.py <logfile> [logfile ...]
"""
import os
import re
import sys

TAG = re.compile(r"^#\s*\[(\S+?)\.([A-Za-z0-9]+)\.(\d+)\]")
WST = re.compile(r"^WSTAT round=\d+ n=(\d+)\s+(.*?)\s+spread=")


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


rows = {}
for path in sys.argv[1:] or []:
    if not os.path.exists(path):
        print("missing: %s" % path)
        continue
    cur = None
    for ln in open(path, errors="replace"):
        m = TAG.match(ln.strip())
        if m:
            cur = int(m.group(3))
            continue
        m = WST.match(ln.strip())
        if not m or cur is None:
            continue
        vals = sorted(float(v) for v in m.group(2).split() if v not in ("-",))
        if len(vals) < 2 or vals[0] <= 0:
            continue
        lo = vals[0]
        rows.setdefault(cur, []).append((
            100.0 * (med(vals) - lo) / lo,        # gain
            100.0 * (vals[1] - lo) / lo,          # gap to second best
            100.0 * (vals[-1] - lo) / lo,         # span
        ))

if not rows:
    sys.exit("no WSTAT lines found -- pass logs written with OGC_WSTAT=1")

print("%-6s %-5s %8s %8s %8s   %s" % ("inst", "runs", "gain", "gap", "span", "reading"))
for p in sorted(rows):
    rs = rows[p]
    g, k, s = (med([r[i] for r in rs]) for i in range(3))
    if k >= 0.5 * g and g > 2.0:
        note = "min rests on ONE worker -- fragile, more draws should pay"
    elif g > 2.0:
        note = "several workers near the min -- robust, more draws buy less"
    else:
        note = "workers agree; the min is not doing much"
    print("P%-5d %-5d %7.2f%% %7.2f%% %7.2f%%   %s" % (p, len(rs), g, k, s, note))

allr = [r for rs in rows.values() for r in rs]
print("\nover %d runs: median gain %.2f%%, gap %.2f%%, span %.2f%%"
      % (len(allr), med([r[0] for r in allr]), med([r[1] for r in allr]),
         med([r[2] for r in allr])))

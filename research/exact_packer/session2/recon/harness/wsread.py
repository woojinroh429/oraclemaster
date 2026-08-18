"""Read results/audit/wspread.log into the two spreads it was run to produce.

Per instance:
  worst   -- the largest objective across replicates, as a percentage over the best.  This is the
             number the request is about: not the average run, the bad one.
  within  -- the median intra-round worker spread, from the WSTAT lines.  Small means nw cores
             produced one draw and more rounds are the lever; large means the minimum is already
             over a real sample.

Prints instances sorted by worst-case penalty, which is the order the rounds A/B should target.

Run: python3.12 harness/wsread.py [logfile]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/wspread.log")

TAG = re.compile(r"^#\s*\[r(\d+)\.p(\d+)\]")
OBJ = re.compile(r"^P\d+\s+\[r(\d+)\.p(\d+)\].*?obj=(\d+).*?feas=(\S+)")
WST = re.compile(r"^WSTAT round=\d+ n=(\d+) (.*?)\s+spread=([\d.]+)%")

runs, within, cur = {}, {}, None
for ln in open(LOG, errors="replace"):
    ln = ln.rstrip("\n")
    m = TAG.match(ln)
    if m:
        cur = (int(m.group(1)), int(m.group(2)))
        continue
    m = WST.match(ln)
    if m and cur:
        within.setdefault(cur[1], []).append(float(m.group(3)))
        continue
    m = OBJ.match(ln)
    if m:
        runs.setdefault(int(m.group(2)), []).append((int(m.group(3)), m.group(4)))


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return float("nan")
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


rows = []
for p, rs in runs.items():
    objs = [o for o, f in rs]
    bad = [f for o, f in rs if f != "y"]
    lo, hi = min(objs), max(objs)
    rows.append((100.0 * (hi - lo) / lo if lo else 0.0, p, len(objs), lo, hi,
                 med(within.get(p, [])), len(bad)))
rows.sort(reverse=True)

print("%-5s %-4s %13s %13s %9s %9s %s" % ("inst", "reps", "best", "worst", "worst%", "within%", "infeas"))
for pen, p, k, lo, hi, w, nb in rows:
    print("P%-4d %-4d %13d %13d %8.2f%% %8.2f%% %s"
          % (p, k, lo, hi, pen, w, nb if nb else "-"))

if rows:
    print("\n%d instances, worst-case penalty median %.2f%%, max %.2f%% (P%d)"
          % (len(rows), med([r[0] for r in rows]), rows[0][0], rows[0][1]))
    _w = [r[5] for r in rows if r[5] == r[5]]
    if _w:
        print("intra-round worker spread: median %.2f%%, min %.2f%%, max %.2f%%"
              % (med(_w), min(_w), max(_w)))

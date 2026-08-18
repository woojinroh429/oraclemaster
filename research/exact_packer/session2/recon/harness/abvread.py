"""Read results/audit/abvar.log as distributions, not as pairs.

Single draws cannot settle either question this experiment asks, so nothing here reports one.
Per instance and arm it prints the replicates, their median, and their WORST -- the worst is the
number the request is about, since a per-instance score pays for the bad draw and not for the
average one.

The arm verdict is deliberately conservative: an arm only "wins" an instance when its worst is
better than the other's worst AND its median is too.  Anything else is called a tie, because with
a handful of replicates against a 3.2-32% run-to-run band that is what the data supports.

`within` is the median intra-round worker spread from the WSTAT lines.  Near zero means the nw
workers converge, the minimum over them is a sample of size one, and more rounds (OGC_ROUNDS,
implemented and defaulting to 1) is the untaken lever on the bad draw.

Run: python3.12 harness/abvread.py [logfile]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/abvar.log")

TAG = re.compile(r"^#\s*\[r(\d+)\.(old|new)\.(\d+)\]")
OBJ = re.compile(r"^P\d+\s+\[r(\d+)\.(old|new)\.(\d+)\].*?obj=(\d+).*?feas=(\S+)")
WST = re.compile(r"^WSTAT round=\d+ n=(\d+) (.*?)\s+spread=([\d.]+)%")

runs, within, cur = {}, {}, None
for ln in open(LOG, errors="replace"):
    ln = ln.rstrip("\n")
    m = TAG.match(ln)
    if m:
        cur = (m.group(2), int(m.group(3)))
        continue
    m = WST.match(ln)
    if m and cur:
        within.setdefault(cur, []).append(float(m.group(3)))
        continue
    m = OBJ.match(ln)
    if m:
        runs.setdefault((m.group(2), int(m.group(3))), []).append((int(m.group(4)), m.group(5)))


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


probs = sorted({p for _, p in runs})
print("%-5s %-4s %-4s %13s %13s %13s %8s %8s  %s"
      % ("inst", "arm", "reps", "best", "median", "worst", "spread", "within", "infeas"))
verdict = {}
for p in probs:
    stat = {}
    for arm in ("old", "new"):
        rs = runs.get((arm, p), [])
        if not rs:
            continue
        objs = [o for o, f in rs]
        bad = sum(1 for o, f in rs if f != "y")
        w = med(within.get((arm, p), []))
        stat[arm] = (med(objs), max(objs), min(objs))
        print("P%-4d %-4s %-4d %13d %13.0f %13d %7.2f%% %s  %s"
              % (p, arm, len(objs), min(objs), med(objs), max(objs),
                 100.0 * (max(objs) - min(objs)) / min(objs) if min(objs) else 0.0,
                 "%7.2f%%" % w if w is not None else "      -",
                 bad if bad else "-"))
    if "old" in stat and "new" in stat:
        om, ow, _ = stat["old"]
        nm, nw, _ = stat["new"]
        verdict[p] = ("new" if (nw < ow and nm < om) else
                      "old" if (ow < nw and om < nm) else "tie")
        print("      -> %s\n" % verdict[p])
    else:
        print()

if verdict:
    from collections import Counter
    c = Counter(verdict.values())
    print("verdict over %d instances: new %d, old %d, tie %d"
          % (len(verdict), c["new"], c["old"], c["tie"]))
    print("(an arm wins only when BOTH its worst and its median beat the other's)")

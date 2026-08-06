"""Read cliff40: where does obj(T) JUMP, and how exposed is each instance to a slow machine?

A cliff is not a slope.  The run-to-run noise on this algorithm is 2.5-16%, so a 20% step between
two budgets is noise and says nothing; the jumps worth finding are the ones already seen -- 42x,
143x, 250x -- where a discrete decision threw completed work away.  So the flag is a RATIO
against the best point on the instance's own curve, not a t-test.

Three verdicts per instance:

    CLIFF   some budget in the ladder returns >2x the instance's best.  A slow machine, or a
            hidden limit at the low end, loses this instance outright.
    ROUGH   no cliff, but the curve is not monotone by more than the noise band -- more budget
            made it worse by >20%.  Timing is steering rather than merely stopping.
    SMOOTH  monotone within noise.  Timing costs a little quality here and nothing more.

Also prints the worker spread at each point, from OGC_WSTAT.  A point where all four workers are
bad is a construction failure; one where three are fine and the minimum rescued it is a
diversification question, and the two want different fixes.

    usage: python3.12 harness/cliffread.py [logfile]
"""
import os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/cliff40.log")
TAG = re.compile(r"^#\s*\[c\.(\d+)\.(\d+)\]")
OBJ = re.compile(r"^P(\d+)\s+\[c\.(\d+)\.(\d+)\].*?obj=(\d+).*?feas=(\S+)")
BAD = re.compile(r"^P(\d+)\s+\[c\.(\d+)\.(\d+)\]\s+HANG")
WST = re.compile(r"^WSTAT round=\d+ n=(\d+)\s+(.*?)\s+spread=([\d.]+)%")

CLIFF_X = 2.0        # a point this many times the instance's best is a cliff
ROUGH_PC = 20.0      # more budget making it >this much worse is beyond the noise band

curves, wstat, bad, cur = {}, {}, [], None
for ln in open(LOG, errors="replace"):
    ln = ln.rstrip("\n")
    m = TAG.match(ln)
    if m:
        cur = (int(m.group(1)), int(m.group(2)))
        continue
    m = WST.match(ln.strip())
    if m and cur:
        wstat[cur] = (int(m.group(1)), m.group(2), float(m.group(3)))
        continue
    m = OBJ.match(ln)
    if m:
        curves.setdefault(int(m.group(2)), {})[int(m.group(3))] = (int(m.group(4)), m.group(5))
        continue
    m = BAD.match(ln)
    if m:
        bad.append((int(m.group(2)), int(m.group(3))))

if not curves:
    sys.exit("no runs yet")

verdicts = {"CLIFF": [], "ROUGH": [], "SMOOTH": [], "partial": []}
for p in sorted(curves, key=lambda q: -len(curves[q])):
    pts = sorted(curves[p].items())
    best = min(v for v, _ in curves[p].values())
    worst_ratio = max(v for v, _ in curves[p].values()) / max(1.0, best)
    # worst step in the wrong direction: more budget, worse answer
    rough = 0.0
    for i in range(1, len(pts)):
        a, b = pts[i - 1][1][0], pts[i][1][0]
        if b > a:
            rough = max(rough, 100.0 * (b - a) / max(1.0, a))
    if len(pts) < 3:
        v = "partial"
    elif worst_ratio > CLIFF_X:
        v = "CLIFF"
    elif rough > ROUGH_PC:
        v = "ROUGH"
    else:
        v = "SMOOTH"
    verdicts[v].append(p)
    print("P%-3d %-7s  worst/best=%6.2fx  worst-uphill=%+6.1f%%" % (p, v, worst_ratio, rough))
    for T, (o, f) in pts:
        w = wstat.get((p, T))
        mark = "  <<< CLIFF" if o > best * CLIFF_X else ""
        print("      %4ds  obj=%-13d feas=%-3s  workers=%-46s spread=%s%s"
              % (T, o, f, (w[1] if w else "-"), ("%.1f%%" % w[2]) if w else "-", mark))
    print()

if bad:
    print("HANG/CRASH: %s\n" % ", ".join("P%d@%ds" % b for b in bad))
for k in ("CLIFF", "ROUGH", "SMOOTH", "partial"):
    if verdicts[k]:
        print("%-7s %2d: %s" % (k, len(verdicts[k]), " ".join("P%d" % p for p in sorted(verdicts[k]))))
print("\nCLIFF instances are the tail the score actually pays for: one of them at the wrong")
print("hidden time limit costs that instance outright, which no median improvement can offset.")

"""Compare arms on what the BEAM produced, not on the final objective.

The final is min(workers) then _z3_improve.  Across 804 runs that pass gained a median of 0.00%
and nothing at all in 419 of them, but three runs gained over 5% -- and one of those three landed
on a single arm of a single instance and produced this session's "-14.5%" permutation headline.
The beam-side difference there was -4.4%.  A metric that is zero half the time and 10% occasionally
does not belong inside an arm comparison; min(workers) is what the search actually built.

    usage: python3.12 harness/beamside.py <logfile> [baseline-arm]
"""
import re, sys, statistics
from collections import defaultdict

LOG = sys.argv[1]
BASE = sys.argv[2] if len(sys.argv) > 2 else None
MARK = re.compile(r"^# \[([^\]]+)\]")
WST = re.compile(r"^WSTAT round=\d+ n=\d+\s+(.*?)\s+spread=([\d.]+)%")
ROW = re.compile(r"^P(\d+)\s+\[([^\]]+)\]\s+\d+s\s+obj=(\d+)")

tag = None; ws = []; sp = None; rec = []
for ln in open(LOG, errors="replace"):
    m = MARK.match(ln)
    if m:
        tag = m.group(1); ws = []; sp = None; continue
    m = WST.match(ln)
    if m and tag:
        ws = [int(x) for x in m.group(1).split() if x.isdigit()]; sp = float(m.group(2)); continue
    m = ROW.match(ln)
    if m and tag and m.group(2) == tag and ws:
        parts = tag.split(".")
        arm = parts[1] if len(parts) > 2 else parts[0]
        w = sorted(ws)
        rec.append((int(m.group(1)), arm, w[0], int(m.group(3)), sp,
                    (w[len(w)//2 - 1] + w[len(w)//2]) / 2.0 if len(w) % 2 == 0 else w[len(w)//2],
                    w[-1]))
        tag = None

if not rec:
    sys.exit("no runs with both worker values and a final")
arms = []
for _, a, _, _, _, _, _ in rec:
    if a not in arms: arms.append(a)
BASE = BASE or arms[0]
base = {p: w for p, a, w, _, _, _, _ in rec if a == BASE}

# THE MIN ALONE IS NOT ENOUGH, AND THE SPREAD IS WORSE THAN NOT ENOUGH.
#
# The answer IS min(workers) and spread is (max-min)/min, so a single lucky low draw improves the
# objective and widens the spread at the same time -- the correlation is forced by the definitions.
# Measured over the 17 instances with 5+ runs: rho(spread, min) = -0.64, but rho(spread, MEDIAN
# worker) = +0.09.  A wide spread says one worker got lucky, not that the search got better.
#
# So print the median worker beside the min.  A genuine improvement moves both; a lucky draw moves
# only the min, and on prob_24 the m3w arm beat ship on the min by 0.19% while its median worker
# was 6.5% worse.
medbase = {p: md for p, a, w, o, s, md, mx in rec if a == BASE}
print("%-5s %-6s %13s %8s %13s %8s   %s" % ("inst", "arm", "min", "vs " + BASE, "median", "vs " + BASE, "spread"))
per = defaultdict(list); perm = defaultdict(list)
for p, a, w, o, s, md, mx in rec:
    d = 100.0 * (w - base[p]) / base[p] if p in base else None
    dm = 100.0 * (md - medbase[p]) / medbase[p] if p in medbase else None
    if d is not None and a != BASE: per[a].append(d)
    if dm is not None and a != BASE: perm[a].append(dm)
    print("P%-4d %-6s %13d %s %13.0f %s %7.2f%%"
          % (p, a, w, ("%+7.2f%%" % d) if d is not None else "%8s" % "-",
             md, ("%+7.2f%%" % dm) if dm is not None else "%8s" % "-", s or 0.0))
print()
for a in arms:
    if a == BASE or not per[a]: continue
    v, vm = per[a], perm[a]
    print("%-6s n=%-2d  min median %+6.2f%% (better %d/%d)   MEDIAN-WORKER median %+6.2f%% (better %d/%d)"
          % (a, len(v), statistics.median(v), sum(1 for x in v if x < 0), len(v),
             statistics.median(vm), sum(1 for x in vm if x < 0), len(vm)))
print()
print("An arm that improves the min but not the median worker got a lucky draw, not a better search.")

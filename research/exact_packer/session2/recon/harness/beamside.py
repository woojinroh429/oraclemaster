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
        rec.append((int(m.group(1)), arm, min(ws), int(m.group(3)), sp))
        tag = None

if not rec:
    sys.exit("no runs with both worker values and a final")
arms = []
for _, a, _, _, _ in rec:
    if a not in arms: arms.append(a)
BASE = BASE or arms[0]
base = {p: w for p, a, w, _, _ in rec if a == BASE}

print("%-5s %-6s %14s %9s %8s   %s" % ("inst", "arm", "best worker", "vs " + BASE, "spread", "polish"))
per = defaultdict(list)
for p, a, w, o, s in rec:
    d = 100.0 * (w - base[p]) / base[p] if p in base else None
    if d is not None and a != BASE: per[a].append(d)
    print("P%-4d %-6s %14d %s %7.2f%%   %+.2f%%"
          % (p, a, w, ("%+8.2f%%" % d) if d is not None else "%9s" % "-", s or 0.0,
             -100.0 * (w - o) / w))
print()
for a in arms:
    if a == BASE or not per[a]: continue
    v = per[a]
    print("%-6s n=%-2d  median %+6.2f%%  better %d/%d  worst %+.2f%%"
          % (a, len(v), statistics.median(v), sum(1 for x in v if x < 0), len(v), max(v)))

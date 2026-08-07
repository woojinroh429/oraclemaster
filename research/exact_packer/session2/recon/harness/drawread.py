"""Decide, from the per-draw beam numbers, why a bigger budget can return a worse answer.

    usage: python3.12 harness/drawread.py results/audit/drawstat.log

Reads the DRAW lines OGC_DRAWSTAT=1 writes -- wid, gen, true axis index, seconds asked, seconds
taken, objective -- and prints the three tables that separate the candidate explanations:

  H1  later draws are worse            -> objective rising with gen; axes 4/5 worst per axis
  H2  the draws are not independent    -> few distinct objectives among the many
  H3  each long draw is worse          -> the 60s best draw beats every 240s draw

The last table is the one that matters for the answer actually reported: the run returns the
minimum over workers, so what a change has to move is the BEST draw, not the mean one.
"""
import re, sys, statistics
from collections import defaultdict

LOG = sys.argv[1] if len(sys.argv) > 1 else "results/audit/drawstat.log"
MARK = re.compile(r"^# \[([^\]]+)\]")
DRAW = re.compile(r"^DRAW wid=(\d+) gen=(\d+) axis=(\S+) ask=([\d.]+) took=([\d.]+) obj=(\d+)")
ROW = re.compile(r"^P(\d+)\s+\[([^\]]+)\]\s+(\d+)s\s+obj=(\d+)")

cells = {}                      # tag -> dict(prob, secs, final, draws=[...])
tag = None
for ln in open(LOG, errors="replace"):
    m = MARK.match(ln)
    if m:
        tag = m.group(1)
        cells.setdefault(tag, {"prob": None, "secs": None, "final": None, "draws": []})
        continue
    m = DRAW.match(ln)
    if m and tag:
        cells[tag]["draws"].append(dict(wid=int(m.group(1)), gen=int(m.group(2)),
                                        axis=m.group(3), ask=float(m.group(4)),
                                        took=float(m.group(5)), obj=int(m.group(6))))
        continue
    m = ROW.match(ln)
    if m and tag and m.group(2) == tag:
        cells[tag].update(prob=int(m.group(1)), secs=int(m.group(3)), final=int(m.group(4)))

live = {t: c for t, c in cells.items() if c["draws"] and c["final"] is not None}
if not live:
    print("no completed DRAWSTAT cells in", LOG); sys.exit(0)

# group by (prob, secs)
grp = defaultdict(list)
for t, c in live.items():
    grp[(c["prob"], c["secs"])].append(c)

def pct(a, b):
    return "%+.2f%%" % (100.0 * (a - b) / b) if b else "n/a"

print("=" * 78)
print("PER CELL   (draws = beam calls across all workers; best = min over draws)")
print("%-6s %5s %4s %7s %12s %12s %12s %7s" %
      ("prob", "secs", "reps", "draws", "best draw", "median draw", "final", "distinct"))
for (p, s), cs in sorted(grp.items()):
    nd = [len(c["draws"]) for c in cs]
    allo = [d["obj"] for c in cs for d in c["draws"] if d["obj"] < float("inf")]
    if not allo:
        continue
    print("%-6s %5d %4d %7.1f %12d %12d %12d %7d" %
          ("P%d" % p, s, len(cs), sum(nd) / len(nd), min(allo),
           int(statistics.median(allo)), int(statistics.median([c["final"] for c in cs])),
           len(set(allo))))

print()
print("=" * 78)
print("H3  IS EACH LONG DRAW WORSE?   best/median draw at each budget, same instance")
for p in sorted({p for p, _ in grp}):
    row = {s: [d["obj"] for c in cs for d in c["draws"]]
           for (pp, s), cs in grp.items() if pp == p}
    if len(row) < 2:
        continue
    lo, hi = min(row), max(row)
    print("  P%-3d  best  %ds %d -> %ds %d   %s" %
          (p, lo, min(row[lo]), hi, min(row[hi]), pct(min(row[hi]), min(row[lo]))))
    print("  P%-3d  med   %ds %d -> %ds %d   %s" %
          (p, lo, int(statistics.median(row[lo])), hi, int(statistics.median(row[hi])),
           pct(statistics.median(row[hi]), statistics.median(row[lo]))))
    print("        (H3 holds if the LONG budget's BEST draw is worse -- then the count is not"
          " the problem)")

print()
print("=" * 78)
print("H1  ARE LATER DRAWS WORSE?   objective by draw number, normalised to that cell's best")
for (p, s), cs in sorted(grp.items()):
    by = defaultdict(list)
    for c in cs:
        b = min(d["obj"] for d in c["draws"])
        for d in c["draws"]:
            by[d["gen"]].append(100.0 * (d["obj"] - b) / b)
    if len(by) < 2:
        continue
    ks = sorted(by)
    print("  P%-3d %4ds  " % (p, s) +
          "  ".join("g%d:%+.1f%%(n%d)" % (k, statistics.median(by[k]), len(by[k]))
                    for k in ks[:12]))

print()
print("=" * 78)
print("H1b WHICH AXIS PAYS?   median excess over the cell's best draw, and wins")
for (p, s), cs in sorted(grp.items()):
    by = defaultdict(list); wins = defaultdict(int)
    for c in cs:
        b = min(d["obj"] for d in c["draws"])
        for d in c["draws"]:
            by[d["axis"]].append(100.0 * (d["obj"] - b) / b)
            if d["obj"] == b:
                wins[d["axis"]] += 1
    if not by:
        continue
    print("  P%-3d %4ds  " % (p, s) +
          "  ".join("ax%s:%+.1f%%/w%d(n%d)" % (a, statistics.median(by[a]), wins[a], len(by[a]))
                    for a in sorted(by)))

print()
print("=" * 78)
print("H2  ARE THE DRAWS INDEPENDENT?   distinct objectives / total draws, per cell")
for (p, s), cs in sorted(grp.items()):
    fr = [(len({d["obj"] for d in c["draws"]}), len(c["draws"])) for c in cs]
    print("  P%-3d %4ds   " % (p, s) +
          "  ".join("%d/%d" % f for f in fr) +
          "     (a low ratio means extra draws are re-sampling the same answer)")

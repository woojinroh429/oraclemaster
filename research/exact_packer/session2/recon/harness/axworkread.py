"""quality(axis, work) -- and what any allocation policy would have scored, from the table alone.

    usage: python3.12 harness/axworkread.py results/audit/axwork.log

Every cell is work-budgeted, so there is no noise term: three repeats of one configuration returned
an identical objective AND an identical placement digest.  A difference printed here is real.

Two questions the table answers without running anything further:

  1. IS ONE AXIS GENERALLY BEST, or is the best axis instance-specific?  If it is instance-specific
     the fix is not a better default axis, it is spending the budget adaptively -- and that is a
     different piece of work.

  2. AT EQUAL TOTAL WORK, does uniform rotation over six axes beat concentrating?  With no clock in
     the search one (axis, work) pair has exactly one answer, so a worker's repeated draws can
     produce at most six distinct results per work level; the choice is really "how much work does
     each of the six get", and the policies below are sums and minima over measured cells.
"""
import re, sys
from collections import defaultdict

LOG = sys.argv[1] if len(sys.argv) > 1 else "results/audit/axwork.log"
ROW = re.compile(r"^P(\d+)\s+\[p(\d+)\.w(\d+)\.a(\d+)\]\s+work=(\d+)\s+.*obj=(\d+|inf)\s+"
                 r"feas=(\w)\s+([\d.]+)s")

Q = {}                                     # (prob, work, axis) -> (obj, secs, feas)
for ln in open(LOG, errors="replace"):
    m = ROW.match(ln)
    if not m:
        continue
    Q[(int(m.group(2)), int(m.group(3)), int(m.group(4)))] = (
        float("inf") if m.group(6) == "inf" else int(m.group(6)),
        float(m.group(8)), m.group(7))

if not Q:
    print("no axwork cells in", LOG); sys.exit(0)

probs = sorted({p for p, _, _ in Q})
works = sorted({w for _, w, _ in Q})
axes = sorted({a for _, _, a in Q})

for p in probs:
    print("=" * 78)
    print("P%-3d   objective by (work per draw, axis).  '*' = best axis at that work" % p)
    print("  %-7s %s" % ("work", "".join("%13s" % ("axis %d" % a) for a in axes)))
    for w in works:
        row = [Q.get((p, w, a)) for a in axes]
        if not any(row):
            continue
        vals = [r[0] if r else None for r in row]
        fin = [v for v in vals if v is not None and v < float("inf")]
        best = min(fin) if fin else None
        cells = []
        for v in vals:
            if v is None:
                cells.append("%13s" % "-")
            elif v == float("inf"):
                cells.append("%13s" % "inf")
            else:
                cells.append("%12d%s" % (v, "*" if v == best else " "))
        print("  %-7d %s" % (w, "".join(cells)))
    # per-axis win count across the work levels measured
    wins = defaultdict(int)
    for w in works:
        fin = {a: Q[(p, w, a)][0] for a in axes if (p, w, a) in Q and Q[(p, w, a)][0] < float("inf")}
        if fin:
            wins[min(fin, key=fin.get)] += 1
    if wins:
        print("  best-axis count over %d work levels: %s"
              % (sum(wins.values()), ", ".join("axis %d x%d" % (a, c) for a, c in sorted(wins.items()))))

print()
print("=" * 78)
print("ALLOCATION POLICIES AT EQUAL TOTAL WORK (min over the draws the policy makes)")
print("  rotate6 = one draw per axis at W/6   |   conc1 = one draw on THIS instance's best axis at W")
print("  conc2   = two draws, the two best axes at W/2")
#
# Priced in TOTAL work spent, not in a matched budget: the concentrating policies are compared at
# whatever total they actually cost, and that total is printed.  A policy that wins while spending
# LESS is a strictly stronger result than one that wins at parity, and forcing parity would have
# thrown away the cells this queue measured.
for p in probs:
    print("  P%-3d" % p)
    for w in works:
        rot = [Q[(p, w, a)][0] for a in axes if (p, w, a) in Q]
        if len(rot) < len(axes):
            continue                                   # incomplete rotation, not comparable
        rotv, rotW = min(rot), w * len(axes)
        for cw in works:
            c1 = [Q[(p, cw, a)][0] for a in axes if (p, cw, a) in Q]
            if not c1:
                continue
            c1v = min(c1)                              # oracle: told this instance's best axis
            c2 = sorted(c1)
            c2v = c2[1] if len(c2) > 1 else None       # two best axes, one draw each
            line = ("    rotate6 W=%-6d %11d  |  conc1 w=%-6d W=%-6d %11d %+8.2f%%"
                    % (rotW, rotv, cw, cw, c1v, 100.0 * (c1v - rotv) / rotv))
            if c2v is not None:
                line += ("  |  conc2 W=%-6d %11d %+8.2f%%"
                         % (2 * cw, min(c1v, c2v), 100.0 * (min(c1v, c2v) - rotv) / rotv))
            print(line)
print()
print("conc1 is an ORACLE: it is told the best axis for this instance. It bounds what any adaptive")
print("policy could win, and if it does not beat rotate6 then axis allocation is not the lever.")

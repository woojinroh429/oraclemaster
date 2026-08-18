"""WHICH _AXES ENTRY ACTUALLY PRODUCES prob_1's GOOD DRAWS.

A WSTAT "draw" is not one construction.  Each worker's `_fresh` is called 8-13 times in a round --
opstat's beam try counts on prob_1 read 12/8/11/8 in a control -- and `axes[gen[0] % 6]` rotates
the axis on every call, so a worker is already a min over about ten constructions spanning all six
axes.  That is why more rounds buy so little: the internal restart is already there.

So the lever is not how many workers or how many rounds; it is WHICH AXIS, and the file's own
measurement says that is the largest variable in the run -- running the six configs separately
moves the objective 32% to 210% while repeating one config moves it 0.0% to 12.6%.

OGC_DRAWSTAT prints one line per construction: wid, generation, TRUE axis index, the slice it was
given and what it returned.  This reads them.

Reported per axis:
    n            how many constructions that axis got
    best         the best objective it ever returned
    P(<= T)      how often a single construction from it beat the target
    median

and per (config, axis), because config A and config B are two different algorithms and an axis may
be worth having in one and not the other.

WHAT WOULD MAKE THIS ACTIONABLE.  If one or two axes hold essentially all the mass below T, then
pinning config-A workers to those -- OGC_AXIS exists and takes an index -- converts the ten
internal constructions from a rotation over six into ten draws of the one that works.  If the good
draws are spread evenly over the axes, the rotation is already right and this is closed.
"""
import re, sys, glob, collections, statistics

TARGET = int(sys.argv[2]) if len(sys.argv) > 2 else 450000
PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 1
FILES = sys.argv[3:] or sorted(glob.glob('results/audit/*.log'))

rows = []
for fn in FILES:
    txt = open(fn, errors='replace').read().split('\n')
    t2p = {}
    for line in txt:
        m = re.match(r'P(\d+)\s+\[(\S+)\]', line)
        if m:
            t2p[m.group(2)] = int(m.group(1))
    tag = None
    for line in txt:
        m = re.match(r'#\s*\[(\S+)\]', line)
        if m:
            tag = m.group(1)
            continue
        m = re.match(r'DRAW wid=(\d+) gen=(\d+) axis=(\S+) ask=([\d.]+) took=([\d.]+) obj=(\d+)', line)
        if m and tag and t2p.get(tag) == PROB:
            rows.append((int(m.group(1)), int(m.group(2)), m.group(3),
                         float(m.group(4)), float(m.group(5)), int(m.group(6))))

if not rows:
    print("no DRAW lines for prob_%d in %d file(s) -- was OGC_DRAWSTAT=1 set?" % (PROB, len(FILES)))
    raise SystemExit

print("prob_%d: %d constructions, target %s\n" % (PROB, len(rows), "{:,}".format(TARGET)))

by = collections.defaultdict(list)
bycfg = collections.defaultdict(list)
for wid, gen, ax, ask, took, obj in rows:
    if obj >= 10 ** 15:
        continue
    by[ax].append(obj)
    bycfg[(wid % 2, ax)].append((obj, ask, took))

print("%-6s %6s %11s %11s %9s %8s" % ("axis", "n", "best", "median", "P(<=T)", "mean s"))
for ax in sorted(by, key=lambda a: -sum(1 for x in by[a] if x <= TARGET) / max(1, len(by[a]))):
    v = sorted(by[ax])
    secs = [t for (w, g, a, k, t, o) in rows if a == ax]
    print("%-6s %6d %11s %11s %8.3f %8.1f"
          % (ax, len(v), "{:,}".format(v[0]), "{:,}".format(int(statistics.median(v))),
             sum(1 for x in v if x <= TARGET) / len(v), statistics.mean(secs) if secs else 0))

print("\nby configuration (0 = even/config A, 1 = odd/config B)")
print("%-4s %-6s %6s %11s %9s" % ("cfg", "axis", "n", "best", "P(<=T)"))
for (c, ax) in sorted(bycfg, key=lambda k: (k[0], -sum(1 for o, _, _ in bycfg[k] if o <= TARGET) / max(1, len(bycfg[k])))):
    v = sorted(o for o, _, _ in bycfg[(c, ax)])
    print("%-4d %-6s %6d %11s %8.3f"
          % (c, ax, len(v), "{:,}".format(v[0]), sum(1 for x in v if x <= TARGET) / len(v)))

# What the rotation costs: a config-A worker's constructions are spread over six axes.  If one axis
# holds the mass, pinning converts n/6 chances into n.
A = {ax: v for (c, ax), raw in bycfg.items() if c == 0 for v in [[o for o, _, _ in raw]]}
if A:
    tot = sum(len(v) for v in A.values())
    best = max(A, key=lambda a: sum(1 for x in A[a] if x <= TARGET) / max(1, len(A[a])))
    p = sum(1 for x in A[best] if x <= TARGET) / max(1, len(A[best]))
    pall = sum(1 for v in A.values() for x in v if x <= TARGET) / max(1, tot)
    print("\nconfig A: best axis is %s at P=%.3f against %.3f for the rotation as a whole." % (best, p, pall))
    for n in (5, 10, 20):
        print("   %2d constructions:  rotation P(any <= T) = %.2f    pinned to %s = %.2f"
              % (n, 1 - (1 - pall) ** n, best, 1 - (1 - p) ** n))

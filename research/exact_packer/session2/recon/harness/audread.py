"""Does beam-time rank survive the operator loop?

The gate on auditioning openings.  For each instance the six axes are ranked twice -- by a 60 s
beam-only run and by a 240 s full run -- and what matters is the RANK correlation between the two
columns, not the objectives themselves.  A prologue that picks openings can only work if the
ordering it sees is the ordering that ends up mattering.

Reports Spearman per instance plus, more directly, whether the axis the audition picks first is
the axis the full run would have picked.  That second number is the one the mechanism actually
depends on: a middling correlation with the top pick usually right is enough, and a high
correlation with the top pick usually wrong is not.

    usage: python3.12 harness/audread.py [logfile]
"""
import os, re, statistics, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results/audit/audition.log")
ROW = re.compile(r"^P(\d+)\s+\[(beam|full)\.a(\d)\.(\d+)\]\s+\d+s\s+obj=(\d+)")

d = {}
for ln in open(LOG, errors="replace"):
    m = ROW.match(ln)
    if m and int(m.group(1)) == int(m.group(4)):
        d[(int(m.group(4)), m.group(2), int(m.group(3)))] = int(m.group(5))

def spear(a, b):
    n = len(a)
    ra = [0] * n; rb = [0] * n
    for i, v in enumerate(sorted(range(n), key=lambda i: a[i])): ra[v] = i
    for i, v in enumerate(sorted(range(n), key=lambda i: b[i])): rb[v] = i
    m = (n - 1) / 2.0
    num = sum((ra[i] - m) * (rb[i] - m) for i in range(n))
    da = (sum((x - m) ** 2 for x in ra)) ** 0.5
    db = (sum((x - m) ** 2 for x in rb)) ** 0.5
    return num / (da * db) if da and db else 0.0

probs = sorted({p for p, _, _ in d})
rhos = []; hit = 0; tot = 0
print("%-5s  %-28s %-28s %7s  %s" % ("inst", "beam 60s rank (best->worst)",
                                     "full 240s rank (best->worst)", "rho", "top pick"))
for p in probs:
    bm = [(k, d.get((p, "beam", k))) for k in range(6)]
    fl = [(k, d.get((p, "full", k))) for k in range(6)]
    if any(v is None for _, v in bm) or any(v is None for _, v in fl):
        print("P%-4d  incomplete" % p); continue
    bo = [k for k, _ in sorted(bm, key=lambda t: t[1])]
    fo = [k for k, _ in sorted(fl, key=lambda t: t[1])]
    r = spear([v for _, v in bm], [v for _, v in fl])
    rhos.append(r); tot += 1
    ok = bo[0] == fo[0]
    hit += ok
    # what picking the audition's best would have cost against the full run's best
    loss = 100.0 * (dict(fl)[bo[0]] - dict(fl)[fo[0]]) / dict(fl)[fo[0]]
    print("P%-4d  %-28s %-28s %+7.2f  a%d vs a%d  %s (+%.2f%%)"
          % (p, " ".join("a%d" % k for k in bo), " ".join("a%d" % k for k in fo),
             r, bo[0], fo[0], "HIT" if ok else "miss", loss))

if rhos:
    print("\nn=%d  median rho %+.2f  top-pick hit %d/%d" % (len(rhos), statistics.median(rhos), hit, tot))
    print("\nrho near +1: beam rank survives, a prologue can select on it.")
    print("rho near  0: the operator loop erases it -- auditioning cannot work, and beam quality")
    print("             does not reach the score either, so improving the beam would not pay.")

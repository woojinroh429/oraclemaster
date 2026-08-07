"""Re-read any arm-vs-arm log split by what the instance's objective is MADE OF.

Every A/B this session was scored by counting wins across a set that turns out not to be one
population.  results/audit/objmix.json puts 30 of the 40 stage-2 instances at 60%+ tardiness and 8
at 60%+ bay preference, with P34 at Z1 = 0 exactly and P2 at Z1 = 98%.  Those are different
optimisation problems sharing a solver, so a mechanism that helps one kind and hurts the other
sums to nothing and reads as "no effect" -- which is the verdict this session recorded, over and
over, on axis sets, dispatch orders, beam aims, rounds and redraws.

This does not re-run anything.  It re-reads logs already on disk and asks the same question inside
each class separately.

    usage: python3.12 harness/bytype.py <logfile> [baseline-arm]

The tag format every queue writes is r<rep>.<arm>.<prob>, so arms and reps come out of the tag and
no per-log configuration is needed.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIX = json.load(open(os.path.join(HERE, "results/audit/objmix.json")))
LOG = sys.argv[1]
BASE = sys.argv[2] if len(sys.argv) > 2 else None
ROW = re.compile(r"^P(\d+)\s+\[r(\d+)\.([A-Za-z0-9_.]+)\.(\d+)\]\s+\d+s\s+obj=(\d+)")
# GUARD: the printed instance and the instance inside the tag must agree.  A line where they
# disagree is not a run -- it appeared twice in this session's notification stream, once as
# "P1 [r1.o5.6] obj=5327658", which is prob_6's objective under prob_1's header.  Reading it
# would have credited one instance with another's result.  The log is the record; a row that
# contradicts itself is dropped.
def _consistent(m):
    return int(m.group(1)) == int(m.group(4))

def klass(p):
    m = MIX.get(str(p))
    if not m:
        return "?"
    z1, _z2, z3 = m
    return "Z1-dom" if z1 >= 60 else ("Z3-dom" if z3 >= 60 else "mixed")

def med(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])

d = {}
for ln in open(LOG, errors="replace"):
    m = ROW.match(ln)
    if m and _consistent(m):
        d.setdefault((int(m.group(4)), m.group(3)), []).append(int(m.group(5)))
if not d:
    sys.exit("no rows in %s" % LOG)

arms = sorted({a for _, a in d})
if BASE is None:
    BASE = "base" if "base" in arms else arms[0]
others = [a for a in arms if a != BASE]
print("%s\nbaseline=%s  arms=%s\n" % (LOG, BASE, ",".join(others)))

for arm in others:
    per = {}
    for p in sorted({q for q, _ in d}):
        a, b = d.get((p, BASE)), d.get((p, arm))
        if not a or not b:
            continue
        ma, mb = med(a), med(b)
        if ma <= 0:
            continue
        per.setdefault(klass(p), []).append((p, 100.0 * (mb - ma) / ma))
    print("  %s" % arm)
    for k in ("Z1-dom", "Z3-dom", "mixed", "?"):
        rows = per.get(k)
        if not rows:
            continue
        dl = [x for _, x in rows]
        print("    %-7s n=%-2d  median %+6.2f%%  better %d / worse %d   %s"
              % (k, len(dl), med(dl), sum(1 for x in dl if x < 0), sum(1 for x in dl if x > 0),
                 " ".join("P%d%+.1f" % r for r in rows)))
    allr = [x for rows in per.values() for _, x in rows]
    if allr:
        print("    %-7s n=%-2d  median %+6.2f%%   <- the number this session reported"
              % ("POOLED", len(allr), med(allr)))
    print()

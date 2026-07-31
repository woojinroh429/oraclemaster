"""Read the better P3 answer instead of guessing at it.

P3's objective is 5*Z2 + 150*Z3 with Z1 always 0, and the deployed build beats our base on BOTH
terms -- Z2 2299 vs 3108, Z3 527 vs 543, so 90,545 against 96,990.  A build that wins on both is
not sitting elsewhere on a trade-off curve; it is finding a better solution outright, and every
knob swept against our base last night returned nothing because the 6.7% lives in machinery our
base does not have.

So stop guessing and read the two solutions side by side.  Both are run here, on the same
instance at the same limit, and compared on the things that can actually differ:

  assignment   how many blocks per bay, and how far each bay's u*load sits from the others --
               Z2 is a RANGE, so it is decided by the extremes, not the average
  preference   which blocks conceded their preferred bay, what each concession cost, and whether
               the two builds concede the SAME blocks or different ones
  overlap      how much of the assignment they agree on at all

The last one decides what kind of difference this is.  High agreement with a better score means
the win is in a handful of specific blocks and is portable.  Low agreement means the two builds
are in different basins and porting a rule will not transfer it.

    python3.12 harness/p3diff.py [PROB] [SECONDS] [MOD_A] [MOD_B]
"""
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402  fixed scorer for both

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
MODA = sys.argv[3] if len(sys.argv) > 3 else "myalgorithm"      # the better one
MODB = sys.argv[4] if len(sys.argv) > 4 else "myalg_base"       # ours

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
pref = [B[b]["bay_preferences"] for b in range(n)]
want = [max(range(m), key=lambda j: pref[b][j]) for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
ar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
u = [(sum(ar) / m) / ar[j] for j in range(m)]


def solve(mod):
    s = importlib.import_module(mod).algorithm(d, SECS)
    o, c = SC._total(d, s)
    bay = {}
    for t, ops in s["operations"].items():
        for op in ops:
            if op["type"] == "ENTRY":
                bay[op["block_id"]] = op["bay_id"]
    return o, c, [bay[b] for b in range(n)]


oa, ca, A = solve(MODA)
ob, cb, Bs = solve(MODB)
print("%-12s obj=%-9d Z2=%-6s Z3=%-7s" % (MODA, int(oa), ca.get("obj2"), ca.get("obj3")))
print("%-12s obj=%-9d Z2=%-6s Z3=%-7s" % (MODB, int(ob), cb.get("obj2"), cb.get("obj3")))
print("   difference: %d  (%.2f%%)" % (int(ob - oa), 100.0 * (ob - oa) / max(1.0, oa)), flush=True)

same = sum(1 for b in range(n) if A[b] == Bs[b])
print("\nASSIGNMENT")
print("   the two agree on %d of %d blocks (%.0f%%)" % (same, n, 100.0 * same / n))
for tag, X in ((MODA, A), (MODB, Bs)):
    load = [0.0] * m
    for b in range(n):
        load[X[b]] += wl[b]
    sc = [u[j] * load[j] for j in range(m)]
    print("   %-12s counts=%s  u*load=%s  range=%.0f"
          % (tag, [X.count(j) for j in range(m)], ["%.0f" % v for v in sc], max(sc) - min(sc)))

print("\nPREFERENCE  (Z3 is the sum of what each block gave up)")
for tag, X in ((MODA, A), (MODB, Bs)):
    lost = [(max(pref[b]) - pref[b][X[b]], b) for b in range(n) if X[b] != want[b]]
    lost.sort(reverse=True)
    print("   %-12s %3d blocks concede, total %4.0f, worst five %s"
          % (tag, len(lost), sum(v for v, _ in lost), [int(v) for v, _ in lost[:5]]))

ca_set = {b for b in range(n) if A[b] != want[b]}
cb_set = {b for b in range(n) if Bs[b] != want[b]}
print("   both concede      : %3d blocks" % len(ca_set & cb_set))
print("   only %-12s: %3d blocks, worth %.0f"
      % (MODA, len(ca_set - cb_set), sum(max(pref[b]) - pref[b][A[b]] for b in ca_set - cb_set)))
print("   only %-12s: %3d blocks, worth %.0f"
      % (MODB, len(cb_set - ca_set), sum(max(pref[b]) - pref[b][Bs[b]] for b in cb_set - ca_set)))

# where the two disagree, is the better build putting blocks where they WANT to be?
dis = [b for b in range(n) if A[b] != Bs[b]]
a_ok = sum(1 for b in dis if A[b] == want[b])
b_ok = sum(1 for b in dis if Bs[b] == want[b])
print("\nDISAGREEMENTS  (%d blocks)" % len(dis))
print("   %-12s puts %d of them in their preferred bay" % (MODA, a_ok))
print("   %-12s puts %d of them in their preferred bay" % (MODB, b_ok))
dz3 = sum((max(pref[b]) - pref[b][Bs[b]]) - (max(pref[b]) - pref[b][A[b]]) for b in dis)
print("   Z3 carried by the disagreements: %+.0f in %s's favour, worth %.0f of objective"
      % (dz3, MODA, dz3 * float(w["w3"])), flush=True)

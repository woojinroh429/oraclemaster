"""Take the deployed build's 90,545 on P3 apart, all the way down.

P3's objective is 5*Z2 + 150*Z3 and Z1 is always 0, so there are exactly two things to explain
and the deployed build wins BOTH -- Z2 2299 vs our 3108, Z3 527 vs our 543.  Winning on both
means it is not trading, it is packing better, and a night of knobs on our base returned nothing
because the mechanism is not a knob.

Z2 = floor(max_j u_j*load_j - min_j u_j*load_j).  It is a RANGE, so only the extreme bays matter
and moving workload between the two middle bays is worth nothing.  Z3 = sum over blocks of
(best preference - preference of the bay it got), so it is decided by WHICH blocks concede, not
how many.

What this prints, and why each piece can carry the answer:

  1 per-bay ledger      counts, workload, u_j, u_j*load_j, which bay sets max and which sets min.
                        Z2's whole value is those two bays; the rest is decoration.
  2 the Z2 gap          how much workload would have to move from the max bay to the min bay to
                        close the range, and whether any block can legally make that move --
                        i.e. whether their Z2 advantage is even reachable from our assignment.
  3 concession ledger   every block that missed its preferred bay, what it paid, how big it is,
                        how much workload it carries.  Printed for both builds and diffed, so
                        "they concede cheaper blocks" and "they concede fewer" are told apart.
  4 preference profile  for the blocks where the two disagree: the full preference vector, what
                        each build chose, and what that choice cost.  This is where a portable
                        rule would show up as a pattern.
  5 demand vs capacity  peak concurrent area demand per bay against bay area, over the whole
                        horizon.  If their winning assignment puts more blocks in a bay that is
                        already at peak, the difference is in the packing, not the assignment.
  6 agreement           how much of the assignment the two share at all, which decides whether
                        any of this is portable or whether they are simply in different basins.

    python3.12 harness/p3deep.py [PROB] [SECONDS] [MOD_A] [MOD_B]
"""
import importlib
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
MODA = sys.argv[3] if len(sys.argv) > 3 else "myalgorithm"
MODB = sys.argv[4] if len(sys.argv) > 4 else "myalg_base"

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
w2, w3 = float(w["w2"]), float(w["w3"])
pref = [B[b]["bay_preferences"] for b in range(n)]
want = [max(range(m), key=lambda j: pref[b][j]) for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]
ar, _bc, _sc = SC._footprint_areas(d)
area = [ar[b] / float(_sc) for b in range(n)]


def solve(mod):
    s = importlib.import_module(mod).algorithm(d, SECS)
    o, c = SC._total(d, s)
    bay, ent, ext = {}, {}, {}
    for t, ops in s["operations"].items():
        for op in ops:
            if op["type"] == "ENTRY":
                bay[op["block_id"]] = op["bay_id"]
                ent[op["block_id"]] = int(t)
            else:
                ext[op["block_id"]] = int(t)
    return o, c, [bay[b] for b in range(n)], ent, ext


def ledger(tag, X):
    load = [0.0] * m
    cnt = [0] * m
    for b in range(n):
        load[X[b]] += wl[b]
        cnt[X[b]] += 1
    sc = [u[j] * load[j] for j in range(m)]
    hi, lo = max(range(m), key=lambda j: sc[j]), min(range(m), key=lambda j: sc[j])
    print("   %s" % tag)
    print("      bay   w x h        area      u      blocks   workload    u*load")
    for j in range(m):
        mark = "  <-- MAX" if j == hi else ("  <-- min" if j == lo else "")
        print("      %-3d %5.0fx%-5.0f %8.0f  %6.3f  %6d  %9.0f  %9.0f%s"
              % (j, bays[j]["width"], bays[j]["height"], bar[j], u[j], cnt[j], load[j],
                 sc[j], mark))
    rng = sc[hi] - sc[lo]
    print("      Z2 = floor(%.0f - %.0f) = %.0f   worth %.0f of objective"
          % (sc[hi], sc[lo], rng, rng * w2))
    return load, sc, hi, lo


oa, ca, A, enA, exA = solve(MODA)
ob, cb, Bs, enB, exB = solve(MODB)
print("=" * 78)
print("P%d   %s obj=%d (Z2 %s, Z3 %s)   |   %s obj=%d (Z2 %s, Z3 %s)"
      % (PROB, MODA, int(oa), ca.get("obj2"), ca.get("obj3"),
         MODB, int(ob), cb.get("obj2"), cb.get("obj3")))
print("      gap = %d, of which Z2 carries %.0f and Z3 carries %.0f"
      % (int(ob - oa), (float(cb["obj2"]) - float(ca["obj2"])) * w2,
         (float(cb["obj3"]) - float(ca["obj3"])) * w3))

print("\n[1] PER-BAY LEDGER")
loadA, scA, hiA, loA = ledger(MODA, A)
loadB, scB, hiB, loB = ledger(MODB, Bs)

print("\n[2] CLOSING THE Z2 GAP")
for tag, load, sc, hi, lo, X in ((MODA, loadA, scA, hiA, loA, A), (MODB, loadB, scB, hiB, loB, Bs)):
    # moving dW of workload from hi to lo changes the range by dW*(u_hi + u_lo)
    need = (sc[hi] - sc[lo]) / (u[hi] + u[lo])
    movable = [b for b in range(n) if X[b] == hi and pref[b][lo] >= pref[b][hi]]
    free_w = sum(wl[b] for b in movable)
    print("   %-12s bay %d -> bay %d needs %.0f workload moved to level the range" % (tag, hi, lo, need))
    print("      %d blocks in bay %d would not lose preference by moving to %d, carrying %.0f"
          % (len(movable), hi, lo, free_w))
    print("      -> %s" % ("enough free workload exists" if free_w >= need
                           else "NOT enough; the rest must be paid for in Z3"))

print("\n[3] CONCESSION LEDGER  (blocks that missed their preferred bay)")
for tag, X in ((MODA, A), (MODB, Bs)):
    lost = [(max(pref[b]) - pref[b][X[b]], b) for b in range(n) if X[b] != want[b]]
    lost.sort(reverse=True)
    tot = sum(v for v, _ in lost)
    print("   %-12s %d blocks, Z3 = %.0f, worth %.0f of objective"
          % (tag, len(lost), tot, tot * w3))
    print("      the ten most expensive:")
    print("         blk  paid   area   workload  wanted  got   preferences")
    for v, b in lost[:10]:
        print("         %-4d %5.0f  %6.0f  %8.0f  %5d  %4d   %s"
              % (b, v, area[b], wl[b], want[b], X[b], [int(x) for x in pref[b]]))

ca_set = {b for b in range(n) if A[b] != want[b]}
cb_set = {b for b in range(n) if Bs[b] != want[b]}
print("   both concede        : %3d blocks" % len(ca_set & cb_set))
print("   only %-12s : %3d blocks costing %.0f"
      % (MODA, len(ca_set - cb_set), sum(max(pref[b]) - pref[b][A[b]] for b in ca_set - cb_set)))
print("   only %-12s : %3d blocks costing %.0f"
      % (MODB, len(cb_set - ca_set), sum(max(pref[b]) - pref[b][Bs[b]] for b in cb_set - ca_set)))
shared = ca_set & cb_set
if shared:
    pa = sum(max(pref[b]) - pref[b][A[b]] for b in shared)
    pb = sum(max(pref[b]) - pref[b][Bs[b]] for b in shared)
    print("   on the %d they BOTH concede: %s pays %.0f, %s pays %.0f  (same blocks, %s bays)"
          % (len(shared), MODA, pa, MODB, pb,
             "same" if all(A[b] == Bs[b] for b in shared) else "different"))

print("\n[4] WHERE THEY DISAGREE")
dis = [b for b in range(n) if A[b] != Bs[b]]
print("   %d of %d blocks placed differently" % (len(dis), n))
dz3 = sum((max(pref[b]) - pref[b][Bs[b]]) - (max(pref[b]) - pref[b][A[b]]) for b in dis)
dwl = [0.0] * m
for b in dis:
    dwl[A[b]] += wl[b]
    dwl[Bs[b]] -= wl[b]
print("   Z3 across them: %+.0f in %s's favour (worth %.0f)" % (dz3, MODA, dz3 * w3))
print("   workload each bay gains under %s: %s" % (MODA, ["%+.0f" % v for v in dwl]))
print("   the twenty biggest disagreements by preference cost:")
print("      blk   area   workload  wanted   %-11s %-11s  preferences" % (MODA, MODB))
rows = sorted(dis, key=lambda b: -abs((max(pref[b]) - pref[b][Bs[b]]) - (max(pref[b]) - pref[b][A[b]])))
for b in rows[:20]:
    print("      %-4d %6.0f  %8.0f  %5d    bay %d (%+.0f)   bay %d (%+.0f)   %s"
          % (b, area[b], wl[b], want[b],
             A[b], -(max(pref[b]) - pref[b][A[b]]),
             Bs[b], -(max(pref[b]) - pref[b][Bs[b]]), [int(x) for x in pref[b]]))

print("\n[5] DEMAND AGAINST CAPACITY  (peak concurrent footprint area per bay)")
for tag, X, en, ex in ((MODA, A, enA, exA), (MODB, Bs, enB, exB)):
    evt = defaultdict(lambda: [0.0] * m)
    for b in range(n):
        evt[en[b]][X[b]] += area[b]
        evt[ex[b]][X[b]] -= area[b]
    cur = [0.0] * m
    peak = [0.0] * m
    for t in sorted(evt):
        for j in range(m):
            cur[j] += evt[t][j]
            peak[j] = max(peak[j], cur[j])
    print("   %-12s peak/capacity per bay: %s"
          % (tag, ["%.0f/%.0f = %.0f%%" % (peak[j], bar[j], 100.0 * peak[j] / bar[j])
                   for j in range(m)]))

print("\n[6] AGREEMENT")
same = n - len(dis)
print("   the two assignments agree on %d of %d blocks (%.0f%%)" % (same, n, 100.0 * same / n))
print("   -> %s" % ("high agreement: the win is a small set of specific blocks and may be portable"
                    if same > 0.8 * n else
                    "low agreement: different basins, a ported rule is unlikely to carry the win"),
      flush=True)

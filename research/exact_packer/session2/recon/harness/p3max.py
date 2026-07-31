"""How much further can the bay-0 trade be pushed, exactly?

The structure of P3, now measured: every block that concedes wanted bay 0; bay 0 is the smallest
(43x23) and carries the largest u (2.078), so it is always the bay that sets Z2's maximum.  Z3
pulls blocks into it and Z2 pushes them out, over the same bay.

The deployed build wins by making that trade better than we do -- it pays 11 more Z3 (1,650) to
buy 1,333 Z2 (6,665).  The question here is whether it goes far enough.

The arithmetic.  Moving workload W out of bay 0 (max) into bay 2 (min):

    dZ2 = -W * (u_0 + u_2) = -2.844 W          worth -14.22 W of objective at w2 = 5
    dZ3 = +g                                    costs +150 g at w3 = 150

so a single block pays for itself whenever g/W < 0.0948.  But Z2 is a RANGE, so the rate holds
only while bay 0 remains the maximum.  From the deployed build's own position that runs out at
W = 691, where Z2 would fall 2300 -> 333.  Whether that is reachable depends on what the bay-0
residents actually cost, which is what this computes:

  1  every bay-0 resident with its workload and what it would pay to move to bay 1 or bay 2
  2  a greedy sweep in ratio order, tracking the TRUE piecewise Z2 (recomputing max and min
     each step, not assuming the slope holds), reporting the objective after each move
  3  the optimum of that sweep, and how far past the deployed build's own answer it sits
  4  an engine feasibility check on the chosen blocks -- the trade is only real if they can
     physically be seated in the destination bay at their own times

Step 4 is the one that can kill it.  Bay 2's peak occupancy is 46%, so there is room by area,
but area is not the constraint the crane rule enforces.

    python3.12 harness/p3max.py [PROB] [SECONDS] [MOD]
"""
import importlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
MOD = sys.argv[3] if len(sys.argv) > 3 else "myalgorithm"

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
w2, w3 = float(w["w2"]), float(w["w3"])
pref = [B[b]["bay_preferences"] for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]

sol = importlib.import_module(MOD).algorithm(d, SECS)
o0, c0 = SC._total(d, sol)
bay, ent, ext = {}, {}, {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            bay[op["block_id"]] = op["bay_id"]
            ent[op["block_id"]] = int(t)
        else:
            ext[op["block_id"]] = int(t)
cur = [bay[b] for b in range(n)]


def z2_of(assign):
    load = [0.0] * m
    for b in range(n):
        load[assign[b]] += wl[b]
    v = [u[j] * load[j] for j in range(m)]
    return math.floor(max(v) - min(v)), v


def z3_of(assign):
    return sum(max(pref[b]) - pref[b][assign[b]] for b in range(n))


z2, vv = z2_of(cur)
z3 = z3_of(cur)
print("%s on P%d: obj=%d  Z2=%d  Z3=%d" % (MOD, PROB, int(o0), z2, z3))
print("   u*load = %s   (max bay %d, min bay %d)"
      % (["%.0f" % x for x in vv], vv.index(max(vv)), vv.index(min(vv))), flush=True)

MAXJ, MINJ = vv.index(max(vv)), vv.index(min(vv))
res = [b for b in range(n) if cur[b] == MAXJ]
print("\n[1] BAY %d RESIDENTS -- what each would pay to leave  (%d blocks, %.0f workload)"
      % (MAXJ, len(res), sum(wl[b] for b in res)))
rows = []
for b in res:
    payj = min((j for j in range(m) if j != MAXJ),
               key=lambda j: pref[b][MAXJ] - pref[b][j])
    pay = pref[b][MAXJ] - pref[b][payj]
    ratio = pay / max(1e-9, wl[b])
    rows.append((ratio, pay, payj, b))
rows.sort()
print("      the twenty cheapest to evict, by preference paid per unit of workload:")
print("         blk  workload   pays  ->bay   pay/load   preferences")
for ratio, pay, payj, b in rows[:20]:
    print("         %-4d %8.0f  %5.0f   %4d   %8.3f   %s"
          % (b, wl[b], pay, payj, ratio, [int(x) for x in pref[b]]))

print("\n[2] GREEDY SWEEP in ratio order, with the TRUE piecewise Z2 recomputed each step")
print("      moved  blk   workload  Z3paid    Z2      objective     delta")
best = (w2 * z2 + w3 * z3, 0, list(cur))
run = list(cur)
obj0 = w2 * z2 + w3 * z3
print("      %5d  %-4s %8s  %6s  %6d  %11d  %9s" % (0, "-", "-", 0, z2, obj0, "-"))
paid = 0.0
for k, (ratio, pay, payj, b) in enumerate(rows, 1):
    run[b] = payj
    zz2, _ = z2_of(run)
    zz3 = z3_of(run)
    obj = w2 * zz2 + w3 * zz3
    paid += pay
    if k <= 25:
        print("      %5d  %-4d %8.0f  %6.0f  %6d  %11d  %+9d"
              % (k, b, wl[b], paid, zz2, obj, obj - obj0))
    if obj < best[0]:
        best = (obj, k, list(run))
print("\n[3] BEST POINT OF THE SWEEP")
bobj, bk, bass = best
bz2, bvv = z2_of(bass)
bz3 = z3_of(bass)
print("   move the %d cheapest out of bay %d:  Z2 %d -> %d,  Z3 %d -> %d"
      % (bk, MAXJ, z2, bz2, z3, bz3))
print("   objective %d -> %d   (%+.2f%%, worth %d)"
      % (int(obj0), int(bobj), 100.0 * (bobj - obj0) / obj0, int(obj0 - bobj)))
print("   u*load after: %s" % ["%.0f" % x for x in bvv])

if bk == 0:
    print("\n   the sweep finds nothing: the incumbent is already at the best point of this trade")
    sys.exit(0)

print("\n[4] CAN THE ENGINE ACTUALLY SEAT THEM?  (each mover, in its new bay, at its own times,")
print("    against every other block left exactly where it is)")
E = SC._ogc_fast_engine(d)
movers = [b for b in range(n) if bass[b] != cur[b]]
ok_n = 0
for b in movers:
    E.clear_all()
    for t, ops in sol["operations"].items():
        for op in ops:
            if op["type"] == "ENTRY" and op["block_id"] != b:
                E.add(int(op["bay_id"]), int(op["block_id"]), int(op["orient_idx"]),
                      float(op["x"]), float(op["y"]), int(ent[op["block_id"]]),
                      int(ext[op["block_id"]]))
    got = len(E.feasible_scan(int(b), [int(bass[b])], int(ent[b]), int(ext[b]), 1))
    ok_n += 1 if got else 0
    if len(movers) <= 30:
        print("      blk %-4d -> bay %d : %s" % (b, bass[b], "%d cells" % got if got else "BLOCKED"))
print("   %d of %d movers have a legal seat in the destination bay at their own entry time"
      % (ok_n, len(movers)))
print("   -> %s" % ("the trade is physically available and the gain above is real"
                    if ok_n == len(movers) else
                    "partially blocked; the reachable part of the gain is smaller than [3] says"),
      flush=True)

"""The one operator P3 has left: swap, priced in closed form.

Single-block eviction from bay 0 is proven exhausted -- break-even needs gap/workload < 0.0948
and the cheapest resident is 0.145, so every move loses.  The reason is structural: every bay-0
resident holds bay 0 as its first choice, so LEAVING always costs Z3 and the trade is one-sided.

A swap is not one-sided.  Exchange a resident a of bay 0 with an applicant b elsewhere:

    dZ2   bay 0's load changes by (w_b - w_a), the other bay's by (w_a - w_b), and Z2 is
          recomputed as the true range -- not assumed linear, because the max and min bays can
          change identity mid-swap.
    dZ3   = [pref_a(0) - pref_a(j)] + [pref_b(j) - pref_b(0)]

The second bracket is NEGATIVE whenever b also wants bay 0, which is the whole point: the
applicant gains preference by coming in while the resident loses it by leaving, so Z3 can fall
even as workload moves.  Evict heavy, admit light, and both terms can improve together.  No
single move can do that.

This was attempted early in the session as swap3, scored through _realise -- an instrument that
returns 43.7% worse when asked to reproduce its own input, so all 58 rejections were
meaningless -- and as swap4, which never ran.  Here the objective delta is exact and needs no
repacking at all, because on P3 Z1 = 0 and the objective is a function of the ASSIGNMENT alone.
The engine is asked only about pairs that are already profitable, and only whether each of the
two blocks has a legal seat in its new bay at its own unchanged times.

    python3.12 harness/p3swap.py [PROB] [SECONDS] [MOD]
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
mxp = [max(pref[b]) for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]

sol = importlib.import_module(MOD).algorithm(d, SECS)
o0, c0 = SC._total(d, sol)
cur, ent, ext, place = [0] * n, {}, {}, {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            cur[op["block_id"]] = op["bay_id"]
            ent[op["block_id"]] = int(t)
            place[op["block_id"]] = (op["orient_idx"], op["x"], op["y"])
        else:
            ext[op["block_id"]] = int(t)


def obj_of(assign):
    load = [0.0] * m
    for b in range(n):
        load[assign[b]] += wl[b]
    v = [u[j] * load[j] for j in range(m)]
    z2 = math.floor(max(v) - min(v))
    z3 = sum(mxp[b] - pref[b][assign[b]] for b in range(n))
    return w2 * z2 + w3 * z3, z2, z3


base, z2, z3 = obj_of(cur)
print("%s on P%d: obj=%d  Z2=%d  Z3=%d   (scorer says %d)"
      % (MOD, PROB, int(base), z2, z3, int(o0)), flush=True)

# every cross-bay pair, priced exactly.  Z1 is 0 and the objective is a function of the
# assignment alone, so this delta is the whole truth -- no repacking, no proxy.
cands = []
for a in range(n):
    for b in range(a + 1, n):
        if cur[a] == cur[b]:
            continue
        alt = list(cur)
        alt[a], alt[b] = cur[b], cur[a]
        o, _z2, _z3 = obj_of(alt)
        if o < base - 1e-9:
            cands.append((o - base, a, b, _z2, _z3))
cands.sort()
print("\n[1] %d of the %d cross-bay swaps improve the objective on their own"
      % (len(cands), sum(1 for a in range(n) for b in range(a + 1, n) if cur[a] != cur[b])))
if not cands:
    print("   the swap neighbourhood is empty too -- this assignment is a local optimum for both")
    print("   single moves and pairwise exchanges, and P3 needs a larger move than either")
    sys.exit(0)

print("   the twenty best, each measured against the incumbent alone:")
print("      delta    blk_a bay wl   pref_a          blk_b bay wl   pref_b          Z2    Z3")
for dlt, a, b, _z2, _z3 in cands[:20]:
    print("      %+8.0f  %-4d %d %5.0f %-14s %-4d %d %5.0f %-14s %5d %5d"
          % (dlt, a, cur[a], wl[a], [int(x) for x in pref[a]],
             b, cur[b], wl[b], [int(x) for x in pref[b]], _z2, _z3))

# apply greedily, re-pricing after each acceptance so the interactions are honest
print("\n[2] GREEDY APPLICATION, re-priced after every acceptance")
run = list(cur)
cure = base
applied = []
while True:
    best = None
    for a in range(n):
        for b in range(a + 1, n):
            if run[a] == run[b]:
                continue
            alt = list(run)
            alt[a], alt[b] = run[b], run[a]
            o, _, _ = obj_of(alt)
            if o < cure - 1e-9 and (best is None or o < best[0]):
                best = (o, a, b)
    if best is None:
        break
    o, a, b = best
    print("      swap %-4d <-> %-4d   obj %d -> %d  (%+d)" % (a, b, int(cure), int(o), int(o - cure)))
    run[a], run[b] = run[b], run[a]
    cure = o
    applied.append((a, b))
fo, fz2, fz3 = obj_of(run)
print("   %d swaps applied: obj %d -> %d  (%+.2f%%),  Z2 %d -> %d,  Z3 %d -> %d"
      % (len(applied), int(base), int(fo), 100.0 * (fo - base) / base, z2, fz2, z3, fz3))

if not applied:
    sys.exit(0)

print("\n[3] CAN THE ENGINE SEAT THE PAIRS?")
print("    A swap must be tested as a PAIR.  Checking each mover against everyone-else-fixed")
print("    asks whether it fits while its own partner is still occupying the destination, which")
print("    is the one thing a swap guarantees is not true.  Both are lifted out, then each is")
print("    asked for a seat in the other's bay at its own unchanged entry window.")
E = SC._ogc_fast_engine(d)


def seat(hold, b, j):
    E.clear_all()
    for q in range(n):
        if q in hold:
            continue
        oi, x, y = place[q]
        E.add(int(cur[q]), int(q), int(oi), float(x), float(y), int(ent[q]), int(ext[q]))
    return len(E.feasible_scan(int(b), [int(j)], int(ent[b]), int(ext[b]), 1))


ok = 0
for (a, b) in applied:
    ja, jb = cur[a], cur[b]
    ca = seat({a, b}, a, jb)
    cb = seat({a, b}, b, ja)
    good = ca > 0 and cb > 0
    ok += 1 if good else 0
    print("      %-4d (bay %d -> %d): %-6s   %-4d (bay %d -> %d): %-6s   %s"
          % (a, ja, jb, ("%d" % ca) if ca else "BLOCK",
             b, jb, ja, ("%d" % cb) if cb else "BLOCK",
             "OK" if good else "swap not seatable"))
print("   %d of %d swaps are seatable as pairs  -> %s"
      % (ok, len(applied),
         "the gain is physically available" if ok == len(applied)
         else "partially blocked; only part of the gain is reachable"), flush=True)

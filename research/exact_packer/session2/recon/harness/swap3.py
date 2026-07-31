"""Swap preference, do not move it.

Every P3 experiment so far MOVED blocks: pick one, send it elsewhere.  That changes bay 0's
occupancy, so Z2 follows, and there is no room to move into -- forcing blocks in raised Z1 from
0 to 105 and the objective 24x.  All of it failed for the same reason.

A swap is a different operator.  Take a block sitting in bay 0 that barely wants it, and a block
outside that badly wants it, and exchange them.  Bay 0's occupancy is preserved, so Z2 barely
moves and the packing has somewhere to put the newcomer -- the space the evicted block vacates.

The gaps make this worth doing, and they are lopsided:

    cheapest bay-0 residents to evict, by what they would pay:   2   5  11  13  15  18  19  20
    most expensive concessions, by what they would gain:        72  58  55  53  49  48  33  28

A block whose gap is 2 is holding a place a block whose gap is 72 wants.  Ten such pairs are
worth Z3 -301, which is 45,150 of objective against a 93,400 baseline.

The first version of this exchanged the two blocks' coordinates and orientations outright, and
all 58 candidates were rejected -- 0 applied.  That was naive: two blocks of similar AREA are not
the same SHAPE, so B does not fit the cell A vacated; their stays differ, so the space A held over
[10,30] is not the space B needs over [50,80]; and the crane rule is checked in four directions
against whatever else is co-resident, which differs entirely between the two slots.  Trading
places is not an operation this problem supports.

So swap the BAY ASSIGNMENT only and let the engine find position, orientation and entry time
again -- which is what _realise does.  One pair at a time, so unlike the bulk perturbations that
raised Z1 from 0 to 105, a failure costs nothing and is simply rolled back.
"""
import importlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as M         # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BUILD = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
DAMAX = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
MOD = sys.argv[4] if len(sys.argv) > 4 else "myalg_base"

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)

sol = importlib.import_module(MOD).algorithm(d, BUILD)
o0, c0 = M._total(d, sol)
print("P%d start obj=%d Z1=%s Z2=%s Z3=%s"
      % (PROB, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3")), flush=True)

rec = {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            rec[op["block_id"]] = {"block_id": op["block_id"], "bay_id": op["bay_id"],
                                   "orient_idx": op["orient_idx"], "x": op["x"], "y": op["y"],
                                   "entry_time": int(t)}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "EXIT":
            rec[op["block_id"]]["exit_time"] = int(t)

ar, _bc, sc = M._footprint_areas(d)
area = [ar[b] / float(sc) for b in range(n)]
pref = [B[b]["bay_preferences"] for b in range(n)]
want = [max(range(m), key=lambda j: pref[b][j]) for b in range(n)]


def pen(b, j):
    return max(pref[b]) - pref[b][j]


# every (resident, outsider) pair where the outsider wants the resident's bay more than the
# resident does, ranked by what the exchange is worth and filtered on how badly the areas differ
pairs = []
for r in range(n):
    jr = rec[r]["bay_id"]
    for q in range(n):
        if q == r or rec[q]["bay_id"] == jr or want[q] != jr:
            continue
        gain = pen(q, rec[q]["bay_id"]) - pen(q, jr)
        pay = pen(r, rec[q]["bay_id"]) - pen(r, jr)
        if gain - pay <= 0:
            continue
        if abs(area[q] - area[r]) > DAMAX:
            continue
        pairs.append((gain - pay, r, q))
pairs.sort(reverse=True)
print("   %d candidate swaps with |area difference| <= %.0f" % (len(pairs), DAMAX), flush=True)

best_o, applied, tried = o0, 0, 0
t0 = time.time()
for val, r, q in pairs:
    if time.time() - t0 > 300:
        break
    if rec[r]["bay_id"] == rec[q]["bay_id"]:
        continue                                    # an earlier swap already moved one of them
    tried += 1
    br, bq = rec[r]["bay_id"], rec[q]["bay_id"]
    wants = [rec[b]["bay_id"] for b in range(n)]
    wants[r], wants[q] = bq, br
    ents = [rec[b]["entry_time"] for b in range(n)]
    exts = [rec[b]["exit_time"] for b in range(n)]
    try:
        s2, spill, _hot = M._realise(d, wants, ents, exts, wait=0)
    except Exception:
        s2 = None
    if s2 is None:
        continue
    ok = M.check_feasibility(d, s2).get("feasible")
    o2 = M._total(d, s2)[0] if ok else float("inf")
    if not (ok and o2 < best_o - 1e-9):
        continue                                    # rejected: rec is untouched, nothing to undo
    best_o = o2
    applied += 1
    # Adopt the re-packed solution wholesale.  _realise re-seats everything, so it may have moved
    # blocks other than the pair to make room, and those moves are part of what was just scored.
    rec = {}
    for t, ops in s2["operations"].items():
        for op in ops:
            if op["type"] == "ENTRY":
                rec[op["block_id"]] = {"block_id": op["block_id"], "bay_id": op["bay_id"],
                                       "orient_idx": op["orient_idx"], "x": op["x"],
                                       "y": op["y"], "entry_time": int(t)}
    for t, ops in s2["operations"].items():
        for op in ops:
            if op["type"] == "EXIT":
                rec[op["block_id"]]["exit_time"] = int(t)
    print("   swap %-3d <-> %-3d  worth %3.0f  spill %d  obj=%d"
          % (r, q, val, spill, int(o2)), flush=True)

s2 = M._build_operations([rec[b] for b in range(n)])
o1, c1 = M._total(d, s2)
print("P%d dA<=%.0f  %d applied of %d tried  obj=%-9d Z1=%s Z2=%s Z3=%s feasible=%s  (%+.2f%%)"
      % (PROB, DAMAX, applied, tried, int(o1), c1.get("obj1"), c1.get("obj2"), c1.get("obj3"),
         M.check_feasibility(d, s2).get("feasible"), 100.0 * (o1 - o0) / o0), flush=True)

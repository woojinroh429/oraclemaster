"""P3 is a balance problem, not a preference problem.

Z3 is closed: all 24 blocks that missed their preferred bay are blocked -- the bay is unavailable
at every entry time that costs no tardiness, so single-block repair recovers exactly none of the
543.  Meanwhile the constructions show Z2 as low as 395 (flatbl) where our pipeline sits at 3108,
so a balanced assignment is physically reachable; flatbl just pays for it with Z3 7528.

The arithmetic that reframes the instance:

    now                 543*150 + 3108*5 = 81,450 + 15,540 = 96,990
    Z3 held, Z2 at 400  81,450 +  2,000            = 83,450

Holding Z3 exactly where it is and only fixing balance lands inside the 70,000-84,000 band the
competition is reported at.  Z2 carries 16% of P3's objective and nothing in this session has
looked at it.

So: what are the per-bay loads, how far from balanced are they, and how much of the gap is
reachable by moves that do NOT touch preference at all -- i.e. moving a block between two bays it
values equally, or into a bay it prefers?  Those moves cannot raise Z3 by construction, so
whatever they recover is free.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import importlib               # noqa: E402
import myalg_orig as M         # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
MOD = sys.argv[2] if len(sys.argv) > 2 else "myalg_base"
LIMIT = {3: 240.0, 4: 480.0, 5: 600.0, 6: 900.0}
T = float(sys.argv[3]) if len(sys.argv) > 3 else LIMIT[PROB]

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)

sol = importlib.import_module(MOD).algorithm(d, T)
o, c = M._total(d, sol)
print("P%d %s  obj=%d  Z1=%s Z2=%s Z3=%s" % (PROB, MOD, int(o), c.get("obj1"), c.get("obj2"),
                                             c.get("obj3")), flush=True)

ent = {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            ent[op["block_id"]] = op["bay_id"]

area = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
avg = sum(area) / m
u = [avg / area[j] for j in range(m)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]

load = [0.0] * m
for b in range(n):
    load[ent[b]] += wl[b]
scaled = [u[j] * load[j] for j in range(m)]
print("   bay      area      u       workload     u*load")
for j in range(m):
    print("   %-3d %9.0f  %5.3f  %11.0f  %9.0f" % (j, area[j], u[j], load[j], scaled[j]))
print("   Z2 = floor(max - min) = %.0f, worth %.0f of the objective (%.1f%%)"
      % (max(scaled) - min(scaled), (max(scaled) - min(scaled)) * w["w2"],
         100.0 * (max(scaled) - min(scaled)) * w["w2"] / o))

# what a perfectly balanced split would look like, ignoring feasibility entirely
tot = sum(load)
ideal = tot / sum(1.0 / u[j] for j in range(m))       # equal u*load across bays
print("   a perfectly balanced assignment gives u*load = %.0f everywhere, Z2 = 0" % ideal)

# moves that cannot cost preference: the block values the destination at least as highly
pref = [B[b]["bay_preferences"] for b in range(n)]
free_moves = defaultdict(list)
for b in range(n):
    here = ent[b]
    for j in range(m):
        if j != here and pref[b][j] >= pref[b][here]:
            free_moves[(here, j)].append(b)
print("   moves that cannot raise Z3 (destination valued >= current):")
tot_free = 0
for (i, j), bs in sorted(free_moves.items()):
    mass = sum(wl[b] for b in bs)
    tot_free += len(bs)
    print("      bay %d -> %d : %3d blocks, %.0f workload" % (i, j, len(bs), mass))
print("   %d such moves exist in total -- whether they PACK is the open question, but no one of"
      " them can cost preference" % tot_free)

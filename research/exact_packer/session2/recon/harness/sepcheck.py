"""Does position actually matter, or is it only a feasibility certificate?

x, y and orientation appear nowhere in w1*Z1 + w2*Z2 + w3*Z3.  All three terms are functions of
(entry time, bay) alone.  If that separation is clean, then throwing away every position in a
good solution and re-packing from scratch -- same bays, same entry times, positions chosen
afresh -- must give back the same objective.  And if it does, the beam has been spending its
budget searching variables the objective cannot see, which is the case for rebuilding the
search over (t, j) instead.

If instead blocks fail to re-seat, the separation is not clean: which positions you chose does
constrain which schedules remain realisable, and a schedule-only search would be chasing
assignments it cannot actually pack.

Takes the best construction we have (flatbl / sac3 / 0.60, 28,261,134 on P6), keeps its bays
and entry times, and re-packs.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import myalg_legacy as A          # noqa: E402  the construction
import myalg_orig as M           # noqa: E402  the scorer and the re-seater

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 6
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
n = len(d["blocks"])

saved = A._CPP_ENGINE_MODE
A._CPP_ENGINE_MODE = A.HAVE_OGC_FAST
try:
    recs = A._smallright_construct(d, max(1.0, SECS - 2.0), small_thresh=0.60,
                                   step=1, mode="flatbl", order="sac3")
finally:
    A._CPP_ENGINE_MODE = saved
assert recs and len(recs) == n, "construction did not complete"
sol = A._build_operations([recs[b] for b in range(n)])
o0, c0 = M._total(d, sol)
print("P%-2d construction   obj=%-11d Z1=%-7s Z2=%-5s Z3=%s"
      % (PROB, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3")), flush=True)

want = [recs[b]["bay_id"] for b in range(n)]
ent = [recs[b]["entry_time"] for b in range(n)]
ext = [recs[b]["exit_time"] for b in range(n)]

t = time.time()
# _realise returns (solution, spill, hot): spill counts blocks that could not take the bay
# they were asked for, which is exactly the quantity in question here.
sol2, spill, hot = M._realise(d, want, ent, ext, wait=0)
el = time.time() - t
if sol2 is None:
    print("   re-pack failed outright in %.0fs -- position is NOT a free variable" % el)
    sys.exit()

o1, c1 = M._total(d, sol2)
fe = M.check_feasibility(d, sol2).get("feasible")
moved = spill
print("P%-2d re-packed      obj=%-11d Z1=%-7s Z2=%-5s Z3=%-7s feasible=%s  (%.0fs)"
      % (PROB, int(o1), c1.get("obj1"), c1.get("obj2"), c1.get("obj3"), fe, el), flush=True)
print("   %d of %d blocks could not keep the bay they were asked for" % (moved, n))
print("   -> %s" % ("position is a free variable: the objective is a function of (t, j) alone"
                    if abs(o1 - o0) < 1e-6 and moved == 0
                    else "position CONSTRAINS the schedule: %+.2f%% and %d blocks displaced"
                         % (100.0 * (o1 - o0) / o0, moved)))

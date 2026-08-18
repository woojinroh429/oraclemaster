"""Beam-GRASP: draw the beam's dispatch order instead of fixing it.

On P5 the beam completes inside its budget and is deterministic -- both cohort arms returned
bit-identical objectives across every repeat -- so every second past the first beam buys
nothing.  That is exactly the pathology the fixed construction had on P6, where it returned the
same answer at 900s as at 120s, and where drawing the order instead of fixing it was worth the
last 2%.

The beam's order is a fixed input it never varies, so the fix is the same: draw the order from
the top-k of what remains under the axis's own priority, run the beam, keep the best by true
objective.  k=1 reproduces the fixed order exactly, so this is a relaxation of the current
behaviour and not a different algorithm.

Where this is NOT worth doing, and why it is only aimed at P3/P4/P5: a beam run costs 65-100s
against the construction's 14, so a 900s budget buys ~9 draws instead of ~60.  The draw
distribution is heavy-tailed -- on P6 one seed needed 34 draws to find its incumbent and another
found a better one at 11 -- so nine draws is far too few to reach the tail.  It is worth doing
only where the beam is the better decoder AND has budget going spare, which is P5 exactly.
"""
import importlib
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402  fixed scorer

PROB = int(sys.argv[1])
BUDGET = float(sys.argv[2])
K = int(sys.argv[3]) if len(sys.argv) > 3 else 4
MOD = sys.argv[4] if len(sys.argv) > 4 else "myalg_base"
SEED = int(sys.argv[5]) if len(sys.argv) > 5 else 777
AXIS = int(sys.argv[6]) if len(sys.argv) > 6 else 1

M = importlib.import_module(MOD)
d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
n = len(d["blocks"])
B = d["blocks"]
rng = random.Random(SEED)
cfg = dict(M._AXES[AXIS % len(M._AXES)])

# the axis's own priority, rebuilt here so draw k=1 reproduces what the beam would have done
AR, _bc, _sc = M._footprint_areas(d)
due = [b["due_date"] for b in B]
pt = [b["processing_time"] for b in B]
rel = [b["release_time"] for b in B]
o = cfg["order"]
if o == "big_first":
    ma = sum(AR) / n
    ordv = [(1 if AR[b] >= 2.0 * ma else 0, due[b], AR[b] * 1e-9) for b in range(n)]
elif o == "defer_big":
    ma = sum(AR) / n
    r0 = max(rel) * 0.2 if rel else 0
    ordv = [(1 if (AR[b] >= 2.0 * ma and rel[b] > r0) else 0, due[b], -AR[b]) for b in range(n)]
elif o == "lst":
    ordv = [(due[b] - pt[b], AR[b] * 1e-9) for b in range(n)]
else:
    ordv = [(due[b], AR[b] * 1e-9) for b in range(n)]
base_order = sorted(range(n), key=lambda b: ordv[b])


def draw(k):
    if k <= 1:
        return list(base_order)
    pool, out = list(base_order), []
    while pool:
        out.append(pool.pop(rng.randrange(min(k, len(pool)))))
    return out


t0 = time.time()
best_o, best_s, draws = float("inf"), None, 0
while time.time() - t0 < BUDGET:
    left = BUDGET - (time.time() - t0)
    if left < 30.0:
        break
    c = dict(cfg, order=draw(K if draws else 1))
    M._OGC_FAST_CACHE.clear()
    s = M._beam_once(d, min(left, 150.0), c)
    draws += 1
    if s is None:
        continue
    ob, _ = SC._total(d, s)
    if ob < best_o:
        best_o, best_s = ob, s
        print("   draw %-3d obj=%-12d  at %.0fs" % (draws, int(ob), time.time() - t0), flush=True)
if best_s is None:
    print("P%d  no beam completed in %.0fs" % (PROB, BUDGET))
    sys.exit(1)
ob, c2 = SC._total(d, best_s)
print("P%-2d BGRASP k=%d axis=%d %d draws in %.0fs  obj=%-12d Z1=%-7s Z2=%-6s Z3=%-8s feasible=%s"
      % (PROB, K, AXIS, draws, time.time() - t0, int(ob), c2.get("obj1"), c2.get("obj2"),
         c2.get("obj3"), SC.check_feasibility(d, best_s).get("feasible")), flush=True)

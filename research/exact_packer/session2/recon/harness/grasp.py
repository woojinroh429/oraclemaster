"""Spend the idle budget on the construction, since the construction is what decides P6.

Where the 900 seconds currently go: 15 to build, 300 to polish -- and the polish provably
converges, because 300s and 800s of it land 28,138,113 to the digit.  So roughly 585 seconds
are idle, on the instance where the construction settles 97% of the objective.

Named orders span a lot: 28.26M for sac3 up to 31.13M for coreperi, and the whole gap between
our best and the target is 4%.  A spread that wide over six hand-written keys says the space
around them is worth sampling rather than choosing from.  _smallright_construct already accepts
an explicit permutation, so no new machinery is needed.

GRASP: build the sac3 priority, then draw an order by repeatedly taking a uniform pick from the
top-k of what remains.  k=1 reproduces sac3 exactly, so the randomisation is a strict relaxation
of the best key we have rather than a departure from it.  Every draw is a complete construction
scored on the true objective, the best is kept, and the polish goes on at the end.

This adds no constant to the algorithm.  It converts budget into quality: more seconds means
more draws, which is the property the fixed-order construction does not have -- it returns the
same answer at 120s as at 900s.
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import myalgorithm as A          # noqa: E402
import myalg_orig as M           # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 6
BUDGET = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
POL = float(sys.argv[3]) if len(sys.argv) > 3 else 300.0
K = int(sys.argv[4]) if len(sys.argv) > 4 else 3
MODE = sys.argv[5] if len(sys.argv) > 5 else "flatbl"
SEED = int(sys.argv[6]) if len(sys.argv) > 6 else 12345

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
n = len(d["blocks"])
w = d["weights"]
B = d["blocks"]

# the sac3 key, rebuilt here so the draws are anchored on the best order we have
ar, _bc, _sc = A._footprint_areas(d)
due = [b["due_date"] for b in B]
pt = [b["processing_time"] for b in B]


def _rank(v, rev):
    o = sorted(range(n), key=lambda i: v[i], reverse=rev)
    r = [0.0] * n
    for p, i in enumerate(o):
        r[i] = p / max(1, n - 1)
    return r


rd, ra = _rank(due, False), _rank(ar, True)
vic = set(sorted(range(n), key=lambda b: -(ar[b] * pt[b]))[:3])
key = [(1 if b in vic else 0, rd[b] + ra[b], due[b]) for b in range(n)]
base_order = sorted(range(n), key=lambda b: key[b])

rng = random.Random(SEED)


def draw(k):
    """A uniform pick from the top-k of what remains, at every position.  k=1 is base_order."""
    if k <= 1:
        return list(base_order)
    pool = list(base_order)
    out = []
    while pool:
        j = rng.randrange(min(k, len(pool)))
        out.append(pool.pop(j))
    return out


def build(order, secs):
    saved = A._CPP_ENGINE_MODE
    A._CPP_ENGINE_MODE = A.HAVE_OGC_FAST
    try:
        return A._smallright_construct(d, secs, small_thresh=0.60, step=1, mode=MODE, order=order)
    finally:
        A._CPP_ENGINE_MODE = saved


TOPN = 4
SHORTPOL = 15.0
t0 = time.time()
best_o, best_recs, draws = float("inf"), None, 0
pool_best = []                      # [(obj, recs)], best first
while time.time() - t0 < BUDGET:
    left = BUDGET - (time.time() - t0)
    if left < 20.0:
        break
    recs = build(draw(K if draws else 1), min(left, 60.0))     # draw 0 is sac3 itself
    draws += 1
    if not recs or len(recs) != n:
        continue
    o, _ = M._total(d, A._build_operations([recs[b] for b in range(n)]))
    pool_best.append((o, recs))
    pool_best.sort(key=lambda t: t[0])
    del pool_best[TOPN:]
    if o < best_o:
        best_o, best_recs = o, recs
        print("   draw %-3d obj=%-11d  at %.0fs" % (draws, int(o), time.time() - t0), flush=True)
if best_recs is None:
    print("P%d  no construction completed in %.0fs" % (PROB, BUDGET))
    sys.exit(1)
o0, c0 = M._total(d, A._build_operations([best_recs[b] for b in range(n)]))
print("P%-2d GRASP k=%d  %d draws in %.0fs   best obj=%-11d Z1=%-7s Z2=%-5s Z3=%s"
      % (PROB, K, draws, time.time() - t0, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3")),
      flush=True)

E = M._ogc_fast_engine(d)
wls = [float(B[b].get("workload", 0.0)) for b in range(n)]


def _polish(recs, secs):
    f = []
    for b in range(n):
        r = recs[b]
        f += [b, r["bay_id"], r["orient_idx"], int(r["x"]), int(r["y"]),
              int(r["entry_time"]), int(r["exit_time"])]
    try:
        o = list(E.z3_reassign(f, float(w["w1"]), float(w["w3"]), float(secs),
                               float(w["w2"]), wls))
    except TypeError:
        o = list(E.z3_reassign(f, float(w["w1"]), float(w["w3"]), float(secs)))
    rr = {}
    for i in range(0, len(o), 7):
        bb = o[i]
        rr[bb] = {"block_id": bb, "bay_id": o[i + 1], "orient_idx": o[i + 2],
                  "x": o[i + 3], "y": o[i + 4], "entry_time": o[i + 5], "exit_time": o[i + 6]}
    return rr, M._total(d, M._build_operations([rr[bb] for bb in range(n)]))[0]


# Re-rank the finalists by what they are worth AFTER polishing.  The polish takes Z2 and Z3, so
# a build holding more of them can finish ahead of one that starts lower -- measured twice, and
# it matters more the shorter the final polish is, because the gap between builds survives.
ranked = []
for o, recs in pool_best:
    _r, po = _polish(recs, SHORTPOL)
    ranked.append((po, o, recs))
    print("   finalist build=%-11d short-polish=%-11d" % (int(o), int(po)), flush=True)
ranked.sort(key=lambda t: t[0])
if ranked[0][1] != pool_best[0][0]:
    print("   -> re-ranked: the best build was NOT the best polished", flush=True)
best_recs = ranked[0][2]

flat = []
for b in range(n):
    r = best_recs[b]
    flat += [b, r["bay_id"], r["orient_idx"], int(r["x"]), int(r["y"]),
             int(r["entry_time"]), int(r["exit_time"])]
try:
    out = list(E.z3_reassign(flat, float(w["w1"]), float(w["w3"]), float(POL), float(w["w2"]), wls))
except TypeError:
    out = list(E.z3_reassign(flat, float(w["w1"]), float(w["w3"]), float(POL)))
r2 = {}
for i in range(0, len(out), 7):
    b = out[i]
    r2[b] = {"block_id": b, "bay_id": out[i + 1], "orient_idx": out[i + 2],
             "x": out[i + 3], "y": out[i + 4], "entry_time": out[i + 5], "exit_time": out[i + 6]}
sol2 = M._build_operations([r2[b] for b in range(n)])
o1, c1 = M._total(d, sol2)
print("P%-2d GRASP k=%d  polished     obj=%-11d Z1=%-7s Z2=%-5s Z3=%-7s feasible=%s"
      % (PROB, K, int(o1), c1.get("obj1"), c1.get("obj2"), c1.get("obj3"),
         M.check_feasibility(d, sol2).get("feasible")), flush=True)
print("   -> %+.2f%% vs the fixed-order 28,138,113" % (100.0 * (o1 - 28138113.0) / 28138113.0))

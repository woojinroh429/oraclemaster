"""Put our polish on top of the construction, the way the deployed build does.

Its P6 answer decomposes exactly: the diagonal construction scores 28,511,119 with Z1 4049,
the final answer is 28,373,827 with Z1 4049 to the digit, and the difference is
(10054-9152)*150 + (1042-793)*8 = 137,292 -- Z2 and Z3 polished while Z1 is never touched.
That is the whole use of the other 877 seconds, and it makes sense of everything measured
tonight: at a demand ratio of 1.14 the tardiness is settled by the construction and no
rearrangement recovers it (our own ruin_tardy found rt_bestrel = 0 on the same instance).

So the question here is narrow.  We have a better construction than the one it polishes --
flatbl/sac3/0.60 at 28,261,134 -- and z3_reassign is the operator that does that polish for us.
Does it recover a comparable amount on top?

Nothing is ported: the construction is called as it stands and the polish is our own operator.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import myalg_legacy as A          # noqa: E402
import myalg_orig as M           # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 6
BUILD = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
POL = float(sys.argv[3]) if len(sys.argv) > 3 else 300.0
MODE = sys.argv[4] if len(sys.argv) > 4 else "flatbl"
ORDER = sys.argv[5] if len(sys.argv) > 5 else "sac3"
THR = float(sys.argv[6]) if len(sys.argv) > 6 else 0.60

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
n = len(d["blocks"])
w = d["weights"]

saved = A._CPP_ENGINE_MODE
A._CPP_ENGINE_MODE = A.HAVE_OGC_FAST
try:
    recs = A._smallright_construct(d, max(1.0, BUILD - 2.0), small_thresh=THR,
                                   step=1, mode=MODE, order=ORDER)
finally:
    A._CPP_ENGINE_MODE = saved
assert recs and len(recs) == n, "construction did not complete"
sol = A._build_operations([recs[b] for b in range(n)])
o0, c0 = M._total(d, sol)
print("P%-2d %s/%s/%.2f  built   obj=%-11d Z1=%-7s Z2=%-5s Z3=%s"
      % (PROB, MODE, ORDER, THR, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3")), flush=True)

flat = []
for b in range(n):
    r = recs[b]
    flat += [b, r["bay_id"], r["orient_idx"], int(r["x"]), int(r["y"]),
             int(r["entry_time"]), int(r["exit_time"])]

E = M._ogc_fast_engine(d)
wls = [float(d["blocks"][b].get("workload", 0.0)) for b in range(n)]
t = time.time()
try:
    out = list(E.z3_reassign(flat, float(w["w1"]), float(w["w3"]), float(POL),
                             float(w["w2"]), wls))
except TypeError:                      # engine without the Z2-aware signature
    out = list(E.z3_reassign(flat, float(w["w1"]), float(w["w3"]), float(POL)))
el = time.time() - t

r2 = {}
for i in range(0, len(out), 7):
    b = out[i]
    r2[b] = {"block_id": b, "bay_id": out[i + 1], "orient_idx": out[i + 2],
             "x": out[i + 3], "y": out[i + 4], "entry_time": out[i + 5], "exit_time": out[i + 6]}
sol2 = M._build_operations([r2[b] for b in range(n)])
o1, c1 = M._total(d, sol2)
fe = M.check_feasibility(d, sol2).get("feasible")
print("P%-2d %s/%s/%.2f  polished obj=%-11d Z1=%-7s Z2=%-5s Z3=%-7s feasible=%s (%.0fs)"
      % (PROB, MODE, ORDER, THR, int(o1), c1.get("obj1"), c1.get("obj2"), c1.get("obj3"), fe, el),
      flush=True)
print("   -> %+.2f%%   Z1 %s -> %s   (the deployed build recovers 137,292 this way, Z1 untouched)"
      % (100.0 * (o1 - o0) / o0, c0.get("obj1"), c1.get("obj1")))

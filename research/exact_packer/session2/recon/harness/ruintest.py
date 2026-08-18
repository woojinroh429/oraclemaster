"""Does tardiness-targeted ruin-recreate find anything?

Not an A/B -- the question is simpler and cheaper: given a finished solution, does the operator
move Z1 at all?  Everything measured on P6 says no single-block move exists (0 of 167 late
blocks could enter at their release with the rest in place), so if several blocks stepping
aside together IS the missing move, this is where it shows.

Reports rounds attempted, rounds kept, and the before/after split of the objective.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalg_v2 as M

p = int(sys.argv[1]); T = float(sys.argv[2]); RT = float(sys.argv[3])
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, 'data/hidden/prob_%d.json' % p)))
n = len(d["blocks"]); w = d["weights"]
sol = M.algorithm(d, T)
o, c = M._total(d, sol)
print("P%d start   obj=%-11d Z1=%-8s Z2=%-6s Z3=%s" % (p, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3")), flush=True)

flat = []
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            flat.append((op["block_id"], op["bay_id"], op["orient_idx"], int(op["x"]), int(op["y"]), int(t)))
ex = {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "EXIT":
            ex[op["block_id"]] = int(t)
F = []
for b, bay, oi, x, y, en in sorted(flat):
    F += [b, bay, oi, x, y, en, ex[b]]

E = M._ogc_fast_engine(d)
if not hasattr(E, "ruin_tardy"):
    print("engine has no ruin_tardy"); sys.exit(1)
wls = [float(d["blocks"][b].get("workload", 0.0)) for b in range(n)]
t0 = time.time()
out = list(E.ruin_tardy(F, float(w["w1"]), float(w["w2"]), float(w["w3"]), wls, RT, 7))
el = time.time() - t0
recs = {}
for i in range(0, len(out), 7):
    b = out[i]
    recs[b] = {"block_id": b, "bay_id": out[i + 1], "orient_idx": out[i + 2],
               "x": out[i + 3], "y": out[i + 4], "entry_time": out[i + 5], "exit_time": out[i + 6]}
s2 = M._build_operations([recs[b] for b in range(n)])
o2, c2 = M._total(d, s2)
print("P%d ruined  obj=%-11d Z1=%-8s Z2=%-6s Z3=%s   %d rounds, %d kept, %.0fs"
      % (p, int(o2), c2.get("obj1"), c2.get("obj2"), c2.get("obj3"),
         E.rt_rounds, E.rt_kept, el), flush=True)
for k in ("rt_nocand", "rt_seated", "rt_unplaceable", "rt_worse", "rt_bestrel", "rt_sumrel", "rt_level"):
    if hasattr(E, k):
        print("   %-16s %s" % (k, getattr(E, k)))
print("   -> %+.2f%%   feasible=%s" % (100.0 * (o2 - o) / o, M.check_feasibility(d, s2).get("feasible")))

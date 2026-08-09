"""WHAT DOES THE EXACT BAY PASS DO WHEN IT IS GIVEN REAL TIME?

prob_1 carries 76.8% of its objective in Z3 (600 * 541 of 422,629) and the aggregate capacity
relaxation admits Z3 = 0 -- give every block its most preferred bay and the three bays sit at
0.28 / 0.63 / 0.80 utilisation.  What holds Z3 where it is must therefore be time windows and 2D
geometry, and the only operator that can rearrange more than two blocks at once is `_assign`:
CP-SAT over every block's bay with the entry times pinned, so Z1 cannot move, plus a Benders loop
that tightens a bay's capacity row whenever the realisation has to spill.

In the run it is registered only as the `bay` operator inside a worker, competing for bandit time
against five others and seeing only that worker's own incumbent.  Wired into the tail it got 24 s
and returned 748,724 against a 438,791 incumbent -- rejected, correctly.  24 s is 2 s per solve
across its 3 cap0 starts x 4 Benders rounds, so that reading says nothing about the operator.

This gives it 30 / 60 / 120 / 240 s on a real incumbent and prints the Z-vector each time, so the
question "is the exact pass starved or is it beaten by the geometry" gets an answer instead of an
inference.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OGC_WSTAT", "")
import myalgorithm as ma

P = int(sys.argv[1]) if len(sys.argv) > 1 else 1
SOLVE = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, "data", "stage2", "prob_%d.json" % P)))

t = time.time()
sol = ma.algorithm(d, SOLVE)
print("solve %.0fs -> %.1fs" % (SOLVE, time.time() - t))
o, z = ma._total(d, sol)
w = d["weights"]
def zs(c):
    if not c:
        return (0.0, 0.0, 0.0)
    return (float(c.get("obj1", 0)), float(c.get("obj2", 0)), float(c.get("obj3", 0)))
def show(tag, o, z):
    z1, z2, z3 = zs(z)
    a = w["w1"] * z1; b = w["w2"] * z2; c = w["w3"] * z3
    print("%-14s obj=%-10.0f Z1=%-8.0f Z2=%-7.0f Z3=%-8.0f   shares %.1f%% / %.1f%% / %.1f%%"
          % (tag, o, z1, z2, z3, 100 * a / o, 100 * b / o, 100 * c / o))
show("incumbent", o, z)

for budget in (30.0, 120.0):
    t = time.time()
    imp = ma._assign(d, sol, budget)
    el = time.time() - t
    if imp is None:
        print("assign %-5.0fs  returned None                                    (%.1fs used)" % (budget, el))
        continue
    o2, z2 = ma._total(d, imp)
    show("assign %.0fs" % budget, o2, z2)
    print("               %+.2f%% against the incumbent                        (%.1fs used)"
          % (100.0 * (o2 / o - 1.0), el))

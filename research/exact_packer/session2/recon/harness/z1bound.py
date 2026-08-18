"""P4, P5 and P6 are tardiness problems.  This bounds the tardiness.

Comparing each instance's Z2+Z3 assignment bound against what we score:

    P3   96,990    bound 36,765   -> 100% of the objective is assignment (Z1 is 0)
    P4  2,531,937  bound 127,374  -> at most 5% is not tardiness
    P5  9,044,458  bound   6,671  -> at most 0.07%
    P6 27,556,165  bound  64,040  -> at most 0.23%

So every preference, balance and contact knob swept on P4/P5/P6 has been fighting over a few
percent at best, and on P5 over one part in fifteen hundred.  The targets are ~12% cuts.  They
can only come from Z1.

The relaxation that bounds Z1: keep the schedule and the assignment, drop the 2D packing and the
crane entirely, and treat each bay as a CUMULATIVE resource whose capacity is its own area.  A
block occupies its footprint area for its processing time somewhere in that bay.  Any feasible
solution to the real problem satisfies this -- blocks that fit side by side in a bay necessarily
fit inside its area -- so the optimum here is a true lower bound on w1*Z1 + w2*Z2 + w3*Z3.

What it buys, beyond the number:

  * how much of our tardiness is forced by capacity and how much is packing waste.  The space-time
    audit put utilisation near 49%, split between the crane sweep (1.6x a block's own footprint)
    and the overhang of the layer union over layer 0 (1.27x).  Neither appears in this model, so
    the gap between this bound and our score is exactly what those two are costing.

  * a target schedule.  The solution is an (assignment, entry time) pair per block that the packer
    can be anchored on, the same way the P3 assignment anchors the beam there.

CAPMUL shrinks every bay to a fraction of its area.  At 1.0 the model is the relaxation and its
answer is a bound.  Below 1.0 it is a MODEL of packing inefficiency: a yard that can only ever
use that fraction of its floor.  P5 comes back with Z1 = 8 at 1.0 against our actual Z1 of about
678, so essentially all of P5's tardiness is geometry -- crane sweep and layer overhang -- and
none of it is capacity.  Sweeping CAPMUL finds the utilisation that reproduces our real Z1, which
both confirms the diagnosis and prices what one point of packing density is worth.

    python3.12 harness/z1bound.py PROB [SECONDS] [OUT.json] [CAPMUL]
"""
import json
import os
import sys

from ortools.sat.python import cp_model

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as M          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 4
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "results/sched_p%d.json" % PROB)
CAPMUL = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
w1, w2, w3 = float(w["w1"]), float(w["w2"]), float(w["w3"])

ar, _bc, sc = M._footprint_areas(d)
area = [int(round(ar[b])) for b in range(n)]
cap = [int(float(bays[j]["width"]) * float(bays[j]["height"]) * sc * CAPMUL) for j in range(m)]

rel = [int(B[b]["release_time"]) for b in range(n)]
pt = [int(B[b]["processing_time"]) for b in range(n)]
due = [int(B[b]["due_date"]) for b in range(n)]
H = max(max(due), max(rel[b] + pt[b] for b in range(n)))
# room for the schedule to run late; without it the model is infeasible rather than tardy
H = H + max(pt) + sum(pt) // max(1, m)

pref = [B[b]["bay_preferences"] for b in range(n)]
gap = [[int(round(max(pref[b]) - pref[b][j])) for j in range(m)] for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]
SCALE = 1000
uw = [[int(round(u[j] * wl[b] * SCALE)) for j in range(m)] for b in range(n)]

mdl = cp_model.CpModel()
start = [mdl.NewIntVar(rel[b], H, "s_%d" % b) for b in range(n)]
end = [mdl.NewIntVar(0, H + max(pt), "e_%d" % b) for b in range(n)]
x = [[mdl.NewBoolVar("x_%d_%d" % (b, j)) for j in range(m)] for b in range(n)]
for b in range(n):
    mdl.AddExactlyOne(x[b])
    mdl.Add(end[b] == start[b] + pt[b])

# one cumulative resource per bay: only the blocks assigned there consume it
for j in range(m):
    ivs, dem = [], []
    for b in range(n):
        iv = mdl.NewOptionalIntervalVar(start[b], pt[b], end[b], x[b][j], "iv_%d_%d" % (b, j))
        ivs.append(iv)
        dem.append(area[b])
    mdl.AddCumulative(ivs, dem, cap[j])

tard = []
for b in range(n):
    t = mdl.NewIntVar(0, H + max(pt), "t_%d" % b)
    mdl.AddMaxEquality(t, [end[b] - due[b], 0])
    tard.append(t)
z1 = mdl.NewIntVar(0, (H + max(pt)) * n, "z1")
mdl.Add(z1 == sum(tard))

hi = sum(max(uw[b][j] for j in range(m)) for b in range(n))
L = [mdl.NewIntVar(0, hi, "L_%d" % j) for j in range(m)]
for j in range(m):
    mdl.Add(L[j] == sum(uw[b][j] * x[b][j] for b in range(n)))
hv = mdl.NewIntVar(0, hi, "hi")
lv = mdl.NewIntVar(0, hi, "lo")
mdl.AddMaxEquality(hv, L)
mdl.AddMinEquality(lv, L)
spread = mdl.NewIntVar(0, hi, "spread")
mdl.Add(spread == hv - lv)

z3 = mdl.NewIntVar(0, sum(max(g) for g in gap), "z3")
mdl.Add(z3 == sum(gap[b][j] * x[b][j] for b in range(n) for j in range(m)))

# scaled by SCALE so Z2's fractional u*load stays integral; divide back out when reporting
mdl.Minimize(int(w1) * SCALE * z1 + int(w2) * spread + int(w3) * SCALE * z3)

slv = cp_model.CpSolver()
slv.parameters.max_time_in_seconds = SECS
slv.parameters.num_search_workers = 4
status = slv.Solve(mdl)
if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    raise SystemExit("no solution: %s" % slv.StatusName(status))

bound = slv.BestObjectiveBound() / SCALE
got = slv.ObjectiveValue() / SCALE
print("P%d  capmul=%.2f  %s: %.0f   %s"
      % (PROB, CAPMUL,
         "lower bound on the FULL objective" if CAPMUL >= 1.0 else "value at this utilisation",
         bound, "(closed)" if status == cp_model.OPTIMAL else "(not closed)"))
print("   best relaxed schedule found: Z1 = %d  Z2 = %.0f  Z3 = %d  ->  %.0f"
      % (slv.Value(z1), slv.Value(spread) / float(SCALE), slv.Value(z3), got))

asg = [max(range(m), key=lambda j: slv.Value(x[b][j])) for b in range(n)]
ent = [slv.Value(start[b]) for b in range(n)]
print("   block counts per bay: %s" % [asg.count(j) for j in range(m)])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"prob": PROB, "assignment": asg, "entry": ent, "z1": slv.Value(z1),
           "z3": slv.Value(z3), "bound": bound}, open(OUT, "w"))
print("   schedule written to %s" % OUT, flush=True)

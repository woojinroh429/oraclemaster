"""How much of the conceded Z3 is forced by capacity alone, before any geometry?

Every P3 repair operator has come back empty: single-block relocation finds 0 of 23 blocks
movable, coordinate swap 0 of 58, bay swap 0 of 58, ejection 0 of 4,849 attempts.  A run of
zeros like that has two readings.  Either the search keeps missing, or the assignment we have is
already near the best any assignment could be and there is nothing to find.

This separates them without searching.  Drop geometry entirely and keep only the one constraint
that cannot be argued with: a bay can hold at most its own area, at every instant.  Charge each
block its footprint area over its stay, and ask for the assignment minimising Z3 subject to each
bay's area-time never being exceeded at any time step.  That is a transportation problem, so the
answer is exact, and because it ignores packing, crane access and integrality of placement, it
is a true LOWER bound on Z3 for this schedule.

    bound close to what we score   ->  the assignment is essentially forced and every zero above
                                       is the correct answer; P3's remaining room is in Z1/Z2 or
                                       in a different schedule, not in preference.
    bound far below what we score  ->  a better assignment exists on paper, and the zeros mean
                                       our operators cannot reach it -- a search problem, worth
                                       attacking with a different construction.

One boolean per (block, bay), one knapsack row per (bay, time step), solved exactly by CP-SAT.
Integral, so the bound is not softened by fractional assignment.
"""
import json
import os
import sys

from ortools.sat.python import cp_model

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as M          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays = d["blocks"], d["bays"]
n, m = len(B), len(bays)
w3 = float(d["weights"]["w3"])

# footprint area per block: the smaller orientation, since the assignment is free to pick it.
# _footprint_areas returns areas pre-scaled by sc, so keep them integral and scale the bay
# capacities the same way rather than dividing back down to floats.
ar, _bc, sc = M._footprint_areas(d)
area = [int(round(ar[b])) for b in range(n)]
cap = [int(float(bays[j]["width"]) * float(bays[j]["height"]) * sc) for j in range(m)]

pref = [B[b]["bay_preferences"] for b in range(n)]
gap = [[int(round(max(pref[b]) - pref[b][j])) for j in range(m)] for b in range(n)]

# Each block occupies [release, release + processing) at the earliest.  Using the EARLIEST
# possible window is what keeps this a bound: any real schedule can only spread the load out
# further in time, never concentrate it more than this.
st = [int(B[b]["release_time"]) for b in range(n)]
en = [st[b] + int(B[b]["processing_time"]) for b in range(n)]
steps = sorted({t for t in st} | {t for t in en})
steps = [t for t in steps if any(st[b] <= t < en[b] for b in range(n))]

mdl = cp_model.CpModel()
x = [[mdl.NewBoolVar("x_%d_%d" % (b, j)) for j in range(m)] for b in range(n)]
for b in range(n):
    mdl.AddExactlyOne(x[b])
nrows = 0
for j in range(m):
    for t in steps:
        live = [b for b in range(n) if st[b] <= t < en[b]]
        if not live:
            continue
        mdl.Add(sum(area[b] * x[b][j] for b in live) <= cap[j])
        nrows += 1
mdl.Minimize(sum(gap[b][j] * x[b][j] for b in range(n) for j in range(m)))

slv = cp_model.CpSolver()
slv.parameters.max_time_in_seconds = 120.0
slv.parameters.num_search_workers = 2
status = slv.Solve(mdl)
if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    raise SystemExit("no solution: %s" % slv.StatusName(status))

lb = slv.BestObjectiveBound()
print("P%d  Z3 lower bound under area-time capacity alone: %.0f  (worth %.0f of objective)"
      % (PROB, lb, lb * w3))
print("   best integral assignment found: Z3 = %d %s"
      % (int(slv.ObjectiveValue()), "(proven optimal)" if status == cp_model.OPTIMAL else ""))
print("   %d (bay, time) capacity rows, %d blocks, %d bays" % (nrows, n, m))
loadj = [sum(1 for b in range(n) if slv.Value(x[b][j])) for j in range(m)]
print("   that assignment puts %s blocks in bays %s"
      % (loadj, list(range(m))))

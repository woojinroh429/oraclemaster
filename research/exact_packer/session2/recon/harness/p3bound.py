"""Is 70,000 a real number on P3, or are we chasing something the instance cannot give?

The assignment bound already in the repo says 47,954 (Z2 6051, Z3 118).  It is not wrong; it is
answering a different question.  It optimises the bay assignment with no notion that a bay can
run out of room, and on P3 that is the binding constraint and not a detail:

    77 of the 200 blocks name bay 0 as their first choice
    those blocks need 90,164 units of area x time
    bay 0 is 43x23 = 989 cells over an 82-step horizon = 81,098

a demand/capacity ratio of 1.11 at PERFECT packing, with the crane rule switched off.  Roughly
eight blocks have to be displaced from bay 0 no matter how well anything is packed, and each
displacement costs its preference gap -- median 47 across this instance, so several hundred
units of Z3 that no search can ever recover.  A bound that does not know this will always
report a gap we cannot close, and reading it as headroom is how a night gets spent on the
wrong thing.

So bound it properly.  Assign blocks to bays minimising w2*Z2 + w3*Z3 (Z1 is 0 here and stays
0: every block has slack) subject to, for each bay, the total area x time of the blocks
assigned to it not exceeding that bay's cells x horizon.  Both sides are relaxations in the
safe direction:

    capacity   cells x horizon ignores the crane rule and ignores that a bay cannot be
               perfectly tiled -- it is an over-estimate of what a bay can hold
    demand     each block contributes its layer-0 footprint CELL COUNT, minimised over
               orientations, not its bounding box -- an under-estimate of what it takes

so any feasible solution to the real problem is feasible here, and the optimum here is a
genuine lower bound on the real optimum.  Z2 enters exactly, through its own range variables,
rather than being dropped.

What the answer means:

    bound >= 80,000    80,000 is out of reach and the target is wrong, not the algorithm
    bound in 70-80k    80,000 is reachable and 70,000 is not; stop paying for the second
    bound << 70,000    both are live and the whole gap is packing efficiency, which is
                       measurable: bay 0 currently runs at 54% peak area occupancy

    python3.12 harness/p3bound.py [PROB] [SECONDS]
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from utils import Block          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
TL = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
w1, w2, w3 = float(w["w1"]), float(w["w2"]), float(w["w3"])
pref = [B[b]["bay_preferences"] for b in range(n)]
mxp = [max(pref[b]) for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
pt = [int(B[b]["processing_time"]) for b in range(n)]
rel = [int(B[b]["release_time"]) for b in range(n)]
due = [int(B[b]["due_date"]) for b in range(n)]
bar = [int(bays[j]["width"]) * int(bays[j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]
HOR = max(due) - min(rel)


def foot_cells(bid):
    """Smallest layer-0 footprint over orientations, in whole cells.  An UNDER-estimate of the
    area the block really needs -- the raster is the polygon's covered cells, and taking the
    minimum over orientations concedes the packer its best case in every direction."""
    best = None
    for oi in range(len(B[bid]["shape"])):
        L = Block(block_id=bid, block_data=B[bid], x=0, y=0, orient_idx=oi).layers_at_pos()[0]
        xs = [p[0] for p in L]; ys = [p[1] for p in L]
        # shoelace: the true polygon area, not the bounding box
        a = 0.0
        for i in range(len(L)):
            x0, y0 = L[i]; x1, y1 = L[(i + 1) % len(L)]
            a += x0 * y1 - x1 * y0
        a = abs(a) / 2.0
        a = min(a, (max(xs) - min(xs)) * (max(ys) - min(ys)))
        best = a if best is None else min(best, a)
    return best or 0.0


area = [foot_cells(b) for b in range(n)]
at = [area[b] * pt[b] for b in range(n)]
cap = [bar[j] * HOR for j in range(m)]

print("P%d: %d blocks, %d bays, horizon %d (releases %d..%d, dues %d..%d)"
      % (PROB, n, m, HOR, min(rel), max(rel), min(due), max(due)))
print("   bay   cells   capacity(cells x horizon)   first-choice demand   ratio")
for j in range(m):
    want = [b for b in range(n) if pref[b].index(max(pref[b])) == j]
    dem = sum(at[b] for b in want)
    print("   %3d %7d %26d %21.0f   %.2f  (%d blocks)"
          % (j, bar[j], cap[j], dem, dem / cap[j], len(want)))
print("   total demand %.0f against total capacity %d  -> %.2f overall"
      % (sum(at), sum(cap), sum(at) / sum(cap)), flush=True)

try:
    from ortools.sat.python import cp_model
except Exception:
    print("\nortools unavailable -- cannot solve the bound")
    sys.exit(0)

SC = 1000                      # Z2 is a floor() of a real range; work in milli-units
M = cp_model.CpModel()
x = [[M.NewBoolVar("x%d_%d" % (b, j)) for j in range(m)] for b in range(n)]
for b in range(n):
    M.AddExactlyOne(x[b])
for j in range(m):
    M.Add(sum(int(round(at[b])) * x[b][j] for b in range(n)) <= int(cap[j]))

# Z2 -- the true range of u_j * load_j, kept exact rather than dropped
uv = [M.NewIntVar(0, int(sum(wl) * max(u) * SC) + 1, "u%d" % j) for j in range(m)]
for j in range(m):
    M.Add(uv[j] == sum(int(round(u[j] * wl[b] * SC)) * x[b][j] for b in range(n)))
hi = M.NewIntVar(0, int(sum(wl) * max(u) * SC) + 1, "hi")
lo = M.NewIntVar(0, int(sum(wl) * max(u) * SC) + 1, "lo")
M.AddMaxEquality(hi, uv)
M.AddMinEquality(lo, uv)
rng = M.NewIntVar(0, int(sum(wl) * max(u) * SC) + 1, "rng")
M.Add(rng == hi - lo)
z2 = M.NewIntVar(0, int(sum(wl) * max(u)) + 1, "z2")          # floor(range)
M.AddDivisionEquality(z2, rng, SC)

z3 = sum(int(mxp[b] - pref[b][j]) * x[b][j] for b in range(n) for j in range(m))
M.Minimize(int(w2) * z2 + int(w3) * z3)

slv = cp_model.CpSolver()
slv.parameters.max_time_in_seconds = TL
slv.parameters.num_search_workers = 4
st = slv.Solve(M)
name = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE"}.get(st, str(st))
if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    print("\nno solution (%s) -- the area relaxation itself is infeasible, which would mean the"
          " instance cannot be packed at all and therefore that the capacity model is wrong"
          % name)
    sys.exit(0)

bz2 = slv.Value(z2)
bz3 = sum(int(mxp[b] - pref[b][j]) for b in range(n) for j in range(m) if slv.Value(x[b][j]))
val = int(slv.ObjectiveValue())
lb = int(slv.BestObjectiveBound())
cnt = [sum(1 for b in range(n) if slv.Value(x[b][j])) for j in range(m)]
print("\n[BOUND]  %s in %.1fs" % (name, slv.WallTime()))
print("   best found  obj=%d   Z2=%d  Z3=%d   blocks per bay %s" % (val, bz2, bz3, cnt))
print("   proven lower bound on the area-relaxed problem: %d" % lb)
print("      (a valid lower bound on the REAL objective too: every real solution satisfies")
print("       these capacities, since the crane rule and imperfect tiling only remove room)")

BEST = 87560
print("\n[WHAT IT MEANS]  our best P3 result is %d." % BEST)
print("   gap to this bound: %d  (%.1f%% of the bound)" % (BEST - lb, 100.0 * (BEST - lb) / lb))
for tgt in (80000, 70000):
    print("   %d is %s" % (tgt, "BELOW the bound -- unreachable, the target is wrong"
                           if tgt < lb else
                           "above the bound, so not excluded by area alone"))
print("\n   the earlier assignment bound (47,954) ignored capacity entirely.  the difference")
print("   between it and this one is what bay 0's overflow costs before any packing happens.")
print("   what remains between this bound and %d is packing efficiency: bay 0 currently runs" % BEST)
print("   at 54%% peak area occupancy, and this bound assumed 100%%.", flush=True)

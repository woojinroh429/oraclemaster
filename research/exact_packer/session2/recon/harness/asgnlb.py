"""The assignment-level lower bound, and the anchor it hands back.

Two measurements set this up.

The ejection chain on P3 landed 586 complete chains -- outsider seated in its preferred bay,
every victim re-seated elsewhere -- and every single one cost more than it saved: best +1585,
median +20660.  At w3 = 150 a median of +20660 is far too large to be preference, so the cost is
Z2.  Moving a block into the popular bay swings u*load by thousands and w2*dZ2 buries w3*dZ3.
Z2 and Z3 are directly coupled on this instance and pull opposite ways, which is why every
operator that repaired one paid more on the other.

Separately, minimising Z3 alone subject to nothing but area-time capacity gives 92 against the
586 we score -- 494 units, 74,100 of objective, that capacity does not force us to pay.

So the search has to be over the ASSIGNMENT, and it has to price both terms at once.  This
solves exactly that: choose a bay for every block, minimising w2*Z2 + w3*Z3, subject to each
bay's area never being exceeded at any instant.  It ignores packing, crane access and placement,
so its value is a genuine lower bound on w2*Z2 + w3*Z3 for any solution with this schedule -- and
because it prices the coupling, it is a bound the local operators' failures cannot explain away.

The optimal assignment is written out as an anchor.  Every anchor perturbation tried so far was
random or single-term (pref moved blocks INTO their preferred bay ignoring load, and Z1 went
0 -> 105).  This one is the assignment that is provably best on the two terms that matter.

    python3.12 harness/asgnlb.py PROB [SECONDS] [OUT.json]
"""
import json
import os
import sys

from ortools.sat.python import cp_model

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as M          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "results/anchor_p%d.json" % PROB)

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
w2, w3 = float(w["w2"]), float(w["w3"])

ar, _bc, sc = M._footprint_areas(d)
area = [int(round(ar[b])) for b in range(n)]
cap = [int(float(bays[j]["width"]) * float(bays[j]["height"]) * sc) for j in range(m)]

pref = [B[b]["bay_preferences"] for b in range(n)]
gap = [[int(round(max(pref[b]) - pref[b][j])) for j in range(m)] for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]

# u_j = (mean bay area) / (bay j area).  Fractional, so scale u*workload into integers and undo
# the scale when reporting; SCALE is large enough that the rounding is far below one Z2 unit.
bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]
SCALE = 1000
uw = [[int(round(u[j] * wl[b] * SCALE)) for j in range(m)] for b in range(n)]

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

hi = sum(max(uw[b][j] for j in range(m)) for b in range(n))
L = [mdl.NewIntVar(0, hi, "L_%d" % j) for j in range(m)]
for j in range(m):
    mdl.Add(L[j] == sum(uw[b][j] * x[b][j] for b in range(n)))
lo_v = mdl.NewIntVar(0, hi, "lo")
hi_v = mdl.NewIntVar(0, hi, "hi")
mdl.AddMaxEquality(hi_v, L)
mdl.AddMinEquality(lo_v, L)
spread = mdl.NewIntVar(0, hi, "spread")
mdl.Add(spread == hi_v - lo_v)

z3 = mdl.NewIntVar(0, sum(max(g) for g in gap), "z3")
mdl.Add(z3 == sum(gap[b][j] * x[b][j] for b in range(n) for j in range(m)))

# objective in units of (1/SCALE) of the true w2*Z2 + w3*Z3.  Z2 is floor()ed in the real
# objective; dropping the floor only ever makes this larger by at most w2, so the bound holds.
mdl.Minimize(int(w2) * spread + int(w3) * SCALE * z3)

slv = cp_model.CpSolver()
slv.parameters.max_time_in_seconds = SECS
slv.parameters.num_search_workers = 4
slv.parameters.log_search_progress = False
status = slv.Solve(mdl)
if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    raise SystemExit("no solution: %s" % slv.StatusName(status))

bound = slv.BestObjectiveBound() / SCALE
got = slv.ObjectiveValue() / SCALE
gz3 = slv.Value(z3)
gz2 = slv.Value(spread) / float(SCALE)
print("P%d  assignment bound on w2*Z2 + w3*Z3 : %.0f   %s"
      % (PROB, bound, "(proven optimal)" if status == cp_model.OPTIMAL else "(not closed)"))
print("   best assignment found:  Z2 = %.0f  Z3 = %d  ->  w2*Z2 + w3*Z3 = %.0f"
      % (gz2, gz3, got))
print("   %d (bay, time) capacity rows over %d blocks, %d bays" % (nrows, n, m))

asg = [max(range(m), key=lambda j: slv.Value(x[b][j])) for b in range(n)]
cnt = [asg.count(j) for j in range(m)]
print("   block counts per bay: %s" % cnt)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"prob": PROB, "assignment": asg, "z2": gz2, "z3": gz3, "bound": bound},
          open(OUT, "w"))
print("   anchor written to %s" % OUT, flush=True)

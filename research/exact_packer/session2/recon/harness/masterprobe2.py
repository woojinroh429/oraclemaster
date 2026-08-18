"""WHICH of the master's two constraints costs the 47,000?

masterprobe settled the time question outright: the assignment master solves to OPTIMAL in
under a second, gap 0.0%, and 8s/1core gives the identical answer to 240s/8cores.  Solver time
is not a lever and never was.

But its optimum is 83,633 against an incumbent of 86,665 -- 3.5%, not the 50,000 the 36,765
bound suggested.  The master is bound by two things at once and the sweep cannot separate them:

    FIXED ENTRY TIMES   ent/ext are pinned from the incumbent so Z1 cannot move
    AREA ROWS           sum(x[b][k]*area[b] over blocks present at t) <= cap[k]*capf[k]

Relaxing capf separates them exactly.  At capf = 1e6 the area rows are vacuous and the model is
"best assignment at these times, geometry ignored".  If that lands near 36,765, the geometry is
what costs the gap and packing work can attack it.  If it stays near 83,000, the ENTRY TIMES are
the binding decision on P3, every bay-reassignment idea has a 3.5% ceiling, and the direction to
abandon is the one I have been pushing all night.

Each row also realises its assignment, so the spill count says how much of any paper gain the
crane rule takes back.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib

mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "myalg_brk")
cache = sys.argv[2] if len(sys.argv) > 2 else "results/p3_incumbent.json"
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, "data/hidden/prob_3.json")))
n = len(d["blocks"]); m = len(d["bays"])
sol = json.load(open(cache))
sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
o0, c0 = mod._total(d, sol)
print("incumbent        obj=%-9d Z2=%s Z3=%s" % (int(o0), c0.get("obj2"), c0.get("obj3")),
      flush=True)

ent = {}; ext = {}; bay = {}
for t_, ops in sol["operations"].items():
    for op in ops:
        b = op["block_id"]
        if op["type"] == "ENTRY":
            ent[b] = int(t_); bay[b] = op["bay_id"]
        else:
            ext[b] = int(t_)

from ortools.sat.python import cp_model

B = d["blocks"]; w = d["weights"]
w2 = float(w.get("w2", 0)); w3 = float(w.get("w3", 0))
pref = [B[b]["bay_preferences"] for b in range(n)]
mxp = [max(pref[b]) for b in range(n)]
area = []
for b in range(n):
    best = None
    for oi in range(len(B[b]["shape"])):
        q = mod._orient_bbox(B[b], oi); a = (q[2] - q[0]) * (q[3] - q[1])
        if best is None or a < best:
            best = a
    area.append(int(round(best)))
cap = [d["bays"][k]["width"] * d["bays"][k]["height"] for k in range(m)]
SC = 1000; avg = sum(cap) / m
U = [int(round(SC * avg / cap[k])) for k in range(m)]


def solve(capf, tl=20.0):
    mdl = cp_model.CpModel()
    x = [[mdl.NewBoolVar("x%d_%d" % (b, k)) for k in range(m)] for b in range(n)]
    for b in range(n):
        mdl.Add(sum(x[b]) == 1)
    ld = [mdl.NewIntVar(0, 10 ** 7, "l%d" % k) for k in range(m)]
    for k in range(m):
        mdl.Add(ld[k] == sum(x[b][k] * int(B[b]["workload"]) for b in range(n)))
    Mv = mdl.NewIntVar(0, 10 ** 12, "M")
    for k in range(m):
        for k2 in range(m):
            if k != k2:
                mdl.Add(Mv >= U[k] * ld[k] - U[k2] * ld[k2])
    if capf < 1e5:
        for k in range(m):
            for tt in sorted(set(ent.values())):
                pres = [b for b in range(n) if ent[b] <= tt < ext[b]]
                if pres:
                    mdl.Add(sum(x[b][k] * area[b] for b in pres) <= int(cap[k] * capf))
    mdl.Minimize(w2 * Mv + w3 * SC * sum(x[b][k] * (mxp[b] - pref[b][k])
                                         for b in range(n) for k in range(m)))
    for b in range(n):
        for k in range(m):
            mdl.AddHint(x[b][k], 1 if bay[b] == k else 0)
    slv = cp_model.CpSolver()
    slv.parameters.max_time_in_seconds = tl
    slv.parameters.num_search_workers = 8
    st = slv.Solve(mdl)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, slv.StatusName(st), None, None
    want = [next(k for k in range(m) if slv.Value(x[b][k]) == 1) for b in range(n)]
    return want, slv.StatusName(st), slv.ObjectiveValue() / SC, slv.BestObjectiveBound() / SC


print("\n  capf = 1e6 means the area rows are DROPPED: best assignment at these times, no geometry")
print("  %-8s %-9s %-11s %-11s %-6s %s" % ("capf", "status", "model obj", "bound", "moved", "realised"))
for capf in (1.0, 1.15, 1.30, 2.0, 1e6):
    want, st, ob, bd = solve(capf)
    if want is None:
        print("  %-8g %s" % (capf, st), flush=True)
        continue
    moved = sum(1 for b in range(n) if want[b] != bay[b])
    r = mod._realise(d, want, ent, ext, 0)
    s, spill = r[0], r[1]
    if s is None:
        real = "FAILED (spill %d)" % spill
    else:
        ot, ct = mod._total(d, s)
        real = "%-9d spill %-3d Z2 %-6s Z3 %s" % (int(ot), spill, ct.get("obj2"), ct.get("obj3"))
    print("  %-8g %-9s %-11.0f %-11.0f %-6d %s" % (capf, st, ob, bd, moved, real), flush=True)

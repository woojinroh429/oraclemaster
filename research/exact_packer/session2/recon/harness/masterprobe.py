"""How good is the ASSIGNMENT MASTER's own answer, and what is stopping it?

WHAT THE CRANE-CUT PROBE ACTUALLY FOUND.  The cut was built on the belief that _assign proposes
a near-bound assignment and _realise rejects it on the descent rule.  cutprobe measured that
belief and it is false: across every start point, _realise spilled ZERO blocks and produced ZERO
cuts.  The master's assignment is realisable exactly as proposed.  So the cut has no input, and
queue27's two arms agreeing to the digit (86635 / Z2 2507 / Z3 494 on both) was not a coincidence
-- it was an inert operator.

WHERE THAT LEAVES THE 50,000 GAP.  On P3 the objective is a pure function of the assignment, and
_assign_once minimises EXACTLY that objective:

    Minimize  w2 * Mv  +  w3 * SC * sum over b,k of x[b][k] * (max_pref[b] - pref[b][k])

with Mv >= U[k]*ld[k] - U[k2]*ld[k2] over every ordered pair.  That is w2*Z2 + w3*Z3 up to the
SC=1000 scaling.  If the master could solve it to optimality and _realise seats the answer with
no spills, we would BE at the bound.  We are at 86,635.

So the question is not the crane rule.  It is how far from optimal the master stops, and the
suspects are stated in its own source:

    slv.parameters.max_time_in_seconds = max(0.5, tl)   # tl = min(left * 0.4, 8.0)
    slv.parameters.num_search_workers  = 1

Eight seconds on one core for 600 booleans with a range objective.  This sweeps the time limit
and the worker count, and reports the solver's own bound alongside its incumbent -- the bound is
what says whether more time can help at all, or whether the model is already closed and the gap
lives somewhere else entirely.

Usage:  masterprobe.py [module] [incumbent.json]
        A saved incumbent is reused if given, so the sweep costs one pipeline run, not five.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib

mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "myalg_brk")
cache = sys.argv[2] if len(sys.argv) > 2 else "results/p3_incumbent.json"
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, "data/hidden/prob_3.json")))
n = len(d["blocks"]); m = len(d["bays"])

# 1.  A REAL incumbent, not the floor.  The floor is Z1-dominated (obj 2.49e9) and its entry
#     times are nothing like the ones _assign actually sees.
if os.path.exists(cache):
    sol = json.load(open(cache))
    sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
    print("incumbent loaded from %s" % cache, flush=True)
else:
    t = time.time()
    sol = mod.algorithm(d, 240.0)
    json.dump(sol, open(cache, "w"))
    print("incumbent built in %.0fs" % (time.time() - t), flush=True)
o0, c0 = mod._total(d, sol)
print("incumbent        obj=%-9d Z1=%s Z2=%s Z3=%s feas=%s"
      % (int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3"), c0.get("feasible")), flush=True)

ent = {}; ext = {}; bay = {}
for t_, ops in sol["operations"].items():
    for op in ops:
        b = op["block_id"]
        if op["type"] == "ENTRY":
            ent[b] = int(t_); bay[b] = op["bay_id"]
        else:
            ext[b] = int(t_)
assert len(ent) == n, (len(ent), n)

# 2.  Rebuild the master's model verbatim, so the numbers are about the shipped model and not
#     about a re-derivation of it, and expose obj / bound / status which _assign_once discards.
from ortools.sat.python import cp_model


def build(capf, cuts=()):
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
    for k in range(m):
        for tt in sorted(set(ent.values())):
            pres = [b for b in range(n) if ent[b] <= tt < ext[b]]
            if pres:
                mdl.Add(sum(x[b][k] * area[b] for b in pres) <= int(cap[k] * capf[k]))
    for _ck, _cs in cuts:
        if len(_cs) > 1:
            mdl.Add(sum(x[q][_ck] for q in _cs) <= len(_cs) - 1)
    mdl.Minimize(w2 * Mv + w3 * SC * sum(x[b][k] * (mxp[b] - pref[b][k])
                                         for b in range(n) for k in range(m)))
    for b in range(n):
        for k in range(m):
            mdl.AddHint(x[b][k], 1 if bay[b] == k else 0)
    return mdl, x, SC


print("\n  the model minimises w2*Mv + w3*SC*pref, i.e. SC=1000 times the true P3 objective")
print("  %-6s %-4s %-11s %-12s %-12s %-7s %s"
      % ("tl", "wrk", "status", "model obj/SC", "model bound/SC", "gap", "realised true obj"))
for tl, wrk in ((8.0, 1), (8.0, 8), (30.0, 8), (120.0, 8), (240.0, 8)):
    mdl, x, SC = build([1.0] * m)
    slv = cp_model.CpSolver()
    slv.parameters.max_time_in_seconds = tl
    slv.parameters.num_search_workers = wrk
    t = time.time()
    st = slv.Solve(mdl)
    el = time.time() - t
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("  %-6.0f %-4d %s" % (tl, wrk, slv.StatusName(st)), flush=True)
        continue
    ob = slv.ObjectiveValue() / SC
    bd = slv.BestObjectiveBound() / SC
    want = [next(k for k in range(m) if slv.Value(x[b][k]) == 1) for b in range(n)]
    r = mod._realise(d, want, ent, ext, 0)
    s, spill = r[0], r[1]
    if s is None:
        real = "realise failed (spill %d)" % spill
    else:
        ot, ct = mod._total(d, s)
        real = "%d  (spill %d, Z2 %s Z3 %s)" % (int(ot), spill, ct.get("obj2"), ct.get("obj3"))
    print("  %-6.0f %-4d %-11s %-12.0f %-12.0f %-7s %s  [%.0fs]"
          % (tl, wrk, slv.StatusName(st), ob, bd,
             "%.1f%%" % (100.0 * (ob - bd) / max(1.0, ob)), real, el), flush=True)

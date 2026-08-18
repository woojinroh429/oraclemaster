"""EXCHANGE, not addition.  Can the target bay hold the 55 blocks the master WANTS in it?

WHAT baycap SETTLED AND WHAT IT DID NOT.  Offering bay 0's 55 residents plus 15 outsiders, the
packer seats 55, 55, 56, 56 as the outsider list grows -- bay 0 saturates at 55-56 blocks and
admits a newcomer only by shedding a resident, nearly one for one.  So the master's uncapped
wish (70 blocks in bay 0, nobody evicted, objective 36,759) is geometrically impossible, and
the capacity-aware bound is not a target.

But that test kept ALL 55 residents in the pool and made the outsiders fight them, which is not
what the master asked for.  Given the measured cardinality as a constraint, the master says:

    bay-0 cap   model obj   blocks per bay      moved
    55          59,709      [55, 75, 70]        15
    56          57,080      [56, 75, 69]        14
    60          47,210      [60, 71, 69]        14
    70          36,759      [70, 63, 67]        16

At a cap of 55 -- bay 0's population UNCHANGED -- the objective is 59,709 against an incumbent
of 86,665.  The route is exchange rather than addition: swap out fifteen residents, swap in
fifteen others, and the bay never grows.  Nothing baycap measured forbids that, because baycap
never offered the packer a set of 55.

THIS TEST.  Take exactly the blocks the capped master wants in bay 0 and ask cranepack, at unit
weights, how many of them it can seat.  Residents keep their entry times; incomers get the same
time windows brk would offer.

    seats ~55   the plan is packable and worth 31% -- the displaced fifteen then need homes in
                bays 1 and 2, which the master's own counts say have room
    seats ~40   the incomers are individually unpackable there and the exchange is a mirage

Reported per cap so the answer is a curve.  cranepack is a heuristic, so a shortfall is
evidence rather than proof -- but a shortfall at every cap, from a warm start that already
seats 55, is the same evidence baycap gave.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib

mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "myalg_brk")
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, "data/hidden/prob_3.json")))
sol = json.load(open("results/p3_incumbent.json"))
sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
n = len(d["blocks"]); m = len(d["bays"]); B = d["blocks"]; w = d["weights"]
w2 = float(w.get("w2", 0)); w3 = float(w["w3"])

import bayrepack as R
import cranepack as CP
from ortools.sat.python import cp_model

pref = [B[b]["bay_preferences"] for b in range(n)]
mxp = [max(p) for p in pref]
pt = [int(B[b]["processing_time"]) for b in range(n)]
rel = [int(B[b]["release_time"]) for b in range(n)]
due = [int(B[b]["due_date"]) for b in range(n)]
bar = [float(d["bays"][j]["width"]) * float(d["bays"][j]["height"]) for j in range(m)]
SC = 1000; avg = sum(bar) / m
U = [int(round(SC * avg / bar[j])) for j in range(m)]

cur = [-1] * n; ent = [-1] * n; ext = [-1] * n; place = {}
for t, ops in sol["operations"].items():
    for op in ops:
        b = op["block_id"]
        if op["type"] == "ENTRY":
            cur[b] = op["bay_id"]; ent[b] = int(t)
            place[b] = (int(op["orient_idx"]), float(op["x"]), float(op["y"]))
        else:
            ext[b] = int(t)
o0, _ = mod._total(d, sol)
TGT = 0
print("incumbent obj=%d   bay %d holds %d   bay counts %s"
      % (int(o0), TGT, sum(1 for b in range(n) if cur[b] == TGT),
         [sum(1 for b in range(n) if cur[b] == j) for j in range(m)]), flush=True)


def master(cap0):
    mdl = cp_model.CpModel()
    x = [[mdl.NewBoolVar("") for j in range(m)] for b in range(n)]
    for b in range(n):
        mdl.Add(sum(x[b]) == 1)
    mdl.Add(sum(x[b][TGT] for b in range(n)) <= cap0)
    ld = [mdl.NewIntVar(0, 10 ** 9, "") for j in range(m)]
    for j in range(m):
        mdl.Add(ld[j] == sum(x[b][j] * int(B[b]["workload"]) for b in range(n)))
    Mv = mdl.NewIntVar(0, 10 ** 12, "")
    for j in range(m):
        for k in range(m):
            if j != k:
                mdl.Add(Mv >= U[j] * ld[j] - U[k] * ld[k])
    mdl.Minimize(w2 * Mv + w3 * SC * sum(x[b][j] * (mxp[b] - pref[b][j])
                                         for b in range(n) for j in range(m)))
    for b in range(n):
        for j in range(m):
            mdl.AddHint(x[b][j], 1 if cur[b] == j else 0)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = 20.0
    s.parameters.num_search_workers = 8
    st = s.Solve(mdl)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, None
    return ([next(j for j in range(m) if s.Value(x[b][j]) == 1) for b in range(n)],
            s.ObjectiveValue() / SC)


def windows(b, nent=3):
    lo, hi = rel[b], due[b] - pt[b]
    if hi < lo:
        return [(ent[b], ent[b] + pt[b])]
    ts = {lo, hi}
    if lo <= ent[b] <= hi:
        ts.add(ent[b])
    for i in range(max(1, nent)):
        ts.add(lo + (hi - lo) * i // max(1, nent - 1) if nent > 1 else lo)
    return [(t, t + pt[b]) for t in sorted(ts)]


print("\n  %-6s %-11s %-8s %-8s %-8s %s"
      % ("cap", "model obj", "wants", "stayers", "incomers", "SEATED by cranepack"))
for cap0 in (55, 56, 60):
    want, ob = master(cap0)
    if want is None:
        print("  %-6d no solution" % cap0, flush=True)
        continue
    S = [b for b in range(n) if want[b] == TGT]
    stay = [b for b in S if cur[b] == TGT]
    come = [b for b in S if cur[b] != TGT]
    blocks_in = []
    for b in S:
        ol, ob2 = R._layers_bbox(B, b)
        blocks_in.append((ol, ob2, windows(b)))
    warm = [(i, place[b][0], int(place[b][1]), int(place[b][2]))
            for i, b in enumerate(S) if cur[b] == TGT]
    W, H = float(d["bays"][TGT]["width"]), float(d["bays"][TGT]["height"])
    t = time.time()
    r = CP.pack(blocks_in, W, H, 4, budget, seed=12345, warm=warm or None, frozen=[],
                weights=[1.0] * len(S))
    got = {loc for (loc, o, x, y, en, ex) in r[1]}
    ncome = sum(1 for i, b in enumerate(S) if cur[b] != TGT and i in got)
    print("  %-6d %-11.0f %-8d %-8d %-8d %d of %d   (incomers seated %d of %d)  [%.0fs]"
          % (cap0, ob, len(S), len(stay), len(come), len(got), len(S), ncome, len(come),
             time.time() - t), flush=True)

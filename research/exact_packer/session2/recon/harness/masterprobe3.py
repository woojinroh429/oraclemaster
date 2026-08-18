"""HOW FAR can we walk toward the bound before the packer refuses?

masterprobe2 established the shape of P3: dropping the area rows puts the assignment master on
36,759 -- the capacity-aware bound to six digits -- at the incumbent's own entry times, by moving
SIXTEEN of 200 blocks.  Realising all sixteen greedily spills 23 and scores 176,390, so the whole
50,000 gap is the packer refusing those moves, not the model failing to find them.

All-or-nothing is the wrong question.  This asks for the best assignment within a HAMMING BALL of
the incumbent -- at most K blocks change bay -- for K from 1 upward.  Two curves come out of it
and they are the two numbers that decide what to build next:

    PAYOFF   what the objective would be if the K moves were seated.  If it is steep early, a
             directed operator that lands three or four moves is worth more than brk's entire
             -15%; if it is flat until K is large, the moves only pay as a set and a
             one-block-at-a-time operator can never collect.
    REFUSAL  how many of those K the packer actually spills.  K moves that seat cleanly are
             free money the pipeline is leaving on the table; K that all spill say the target
             bay has to be REPACKED to admit them, which is exactly brk's job and tells us to
             point brk at the master's wish list instead of at its pressure heuristic.

The realisation here is the plain greedy one, so a spill is evidence and not proof -- brk exists
precisely because freeing positions admits blocks the fixed-position scan refuses.  Read the
spill column as an upper bound on the difficulty, not as a verdict.
"""
import sys, os, json
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
print("incumbent  obj=%d  Z2=%s  Z3=%s" % (int(o0), c0.get("obj2"), c0.get("obj3")), flush=True)

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
cap = [d["bays"][k]["width"] * d["bays"][k]["height"] for k in range(m)]
SC = 1000; avg = sum(cap) / m
U = [int(round(SC * avg / cap[k])) for k in range(m)]


def solve(K):
    """Best assignment with at most K blocks moved off the incumbent.  Area rows dropped --
    masterprobe2 showed they cost 47,000 and describe a relaxation the packer does not obey."""
    mdl = cp_model.CpModel()
    x = [[mdl.NewBoolVar("x%d_%d" % (b, k)) for k in range(m)] for b in range(n)]
    for b in range(n):
        mdl.Add(sum(x[b]) == 1)
    mdl.Add(sum(1 - x[b][bay[b]] for b in range(n)) <= K)
    ld = [mdl.NewIntVar(0, 10 ** 7, "l%d" % k) for k in range(m)]
    for k in range(m):
        mdl.Add(ld[k] == sum(x[b][k] * int(B[b]["workload"]) for b in range(n)))
    Mv = mdl.NewIntVar(0, 10 ** 12, "M")
    for k in range(m):
        for k2 in range(m):
            if k != k2:
                mdl.Add(Mv >= U[k] * ld[k] - U[k2] * ld[k2])
    mdl.Minimize(w2 * Mv + w3 * SC * sum(x[b][k] * (mxp[b] - pref[b][k])
                                         for b in range(n) for k in range(m)))
    for b in range(n):
        for k in range(m):
            mdl.AddHint(x[b][k], 1 if bay[b] == k else 0)
    slv = cp_model.CpSolver()
    slv.parameters.max_time_in_seconds = 30.0
    slv.parameters.num_search_workers = 8
    st = slv.Solve(mdl)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, slv.StatusName(st), None
    return ([next(k for k in range(m) if slv.Value(x[b][k]) == 1) for b in range(n)],
            slv.StatusName(st), slv.ObjectiveValue() / SC)


print("\n  %-4s %-9s %-11s %-6s %-7s %s"
      % ("K", "status", "if seated", "moved", "spill", "realised (greedy)"))
for K in (1, 2, 3, 4, 6, 8, 12, 16, 24):
    want, st, ob = solve(K)
    if want is None:
        print("  %-4d %s" % (K, st), flush=True)
        continue
    mv = [b for b in range(n) if want[b] != bay[b]]
    r = mod._realise(d, want, ent, ext, 0)
    s, spill = r[0], r[1]
    if s is None:
        real = "FAILED (spill %d)" % spill
    else:
        ot, ct = mod._total(d, s)
        real = "%-9d Z2 %-6s Z3 %s" % (int(ot), ct.get("obj2"), ct.get("obj3"))
    print("  %-4d %-9s %-11.0f %-6d %-7s %s" % (K, st, ob, len(mv), spill, real), flush=True)
    if K <= 4:
        print("       moves: %s" % ", ".join("b%d %d->%d" % (b, bay[b], want[b]) for b in mv),
              flush=True)

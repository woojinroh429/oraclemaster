"""Regrow from the assignment that is provably best on the two terms that matter.

asgnlb proves the optimum over bay assignments, subject only to area-time capacity:

    ours                Z2 2943   Z3 586   ->  102,615
    assignment optimum  Z2 6051   Z3 118   ->   47,954   (proven optimal)

It buys preference by SPENDING balance -- Z2 more than doubles.  That is the correct trade at
w3/w2 = 30 and it is the opposite of what our pipeline does, which is why every repair operator
came back empty: each was charged w2*dZ2 for a move whose w3*dZ3 payoff it could only collect a
block at a time.

Every earlier anchor perturbation was random or single-term.  The `pref` shake moved blocks into
their preferred bay ignoring load and Z1 went 0 -> 105.  This anchor is different: it is priced
on both terms at once and it respects capacity at every instant, so the load it asks for is one
the yard can physically hold.

stay is in OBJECTIVE UNITS, not a fraction.  The C++ adds it straight into

    drank = w1*tardy + w3*pen - mu*contact + w2*dobj2

for any bay other than the anchored one, decayed by dispatch position.  The pipeline knows this
and passes w3 * 4^(1 - g%3), which is 37 to 600 on P3.  shake.py passed 0.6 and the first cut of
this file passed 1.0 -- against terms of order 150 to 17778, an anchor roughly 250x too weak to
bend a single decision.  So shake.py's three perturbation experiments, all of which reported no
improvement, were measured with the anchor effectively switched off.  The sweep here is scaled by
w3 so the values mean something: 0.25x barely suggests, 40x is close to enforcement.

    python3.12 harness/anchorrun.py PROB BUDGET [MOD] [STAY_MULTIPLES_OF_W3]
"""
import importlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402  fixed scorer

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BUDGET = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
MOD = sys.argv[3] if len(sys.argv) > 3 else "myalg_base"
MULTS = [float(x) for x in (sys.argv[4].split(",") if len(sys.argv) > 4 else
                            ["0.25", "1", "4", "40"])]

M = importlib.import_module(MOD)
d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
n, m = len(d["blocks"]), len(d["bays"])

anc = json.load(open(os.path.join(HERE, "results/anchor_p%d.json" % PROB)))
asg = [int(v) for v in anc["assignment"]]
print("P%d anchor from asgnlb: Z2 %.0f  Z3 %d  bound %.0f  counts %s"
      % (PROB, anc["z2"], anc["z3"], anc["bound"], [asg.count(j) for j in range(m)]), flush=True)

sol = M.algorithm(d, BUDGET)
o0, c0 = SC._total(d, sol)
bay0, order0 = SC._anchor_of(d, sol)
print("P%d %s incumbent obj=%d Z1=%s Z2=%s Z3=%s   counts %s"
      % (PROB, MOD, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3"),
         [list(bay0).count(j) for j in range(m)]), flush=True)
print("   the anchor moves %d of %d blocks to a different bay"
      % (sum(1 for b in range(n) if asg[b] != bay0[b]), n), flush=True)

cfg = dict(M._AXES[1])
w3v = float(d["weights"]["w3"])
best_o, best_s = o0, sol

# The incumbent is the FULL pipeline -- beam, balance, z3_improve, several regrows, best-of.
# A single anchored _regrow is one beam.  Scoring one against the other measures the missing
# polish, not the anchor, so each stay is run twice: once on the CP-SAT assignment and once on
# the incumbent's own assignment, same budget, same everything else.  The control is the
# baseline; the incumbent is only there for scale.
for mult in MULTS:
    stay = w3v * mult
    t0 = time.time()
    try:
        ctl = M._regrow(d, sol, BUDGET, cfg, stay=stay, anchor=(list(bay0), order0))
        oc = SC._total(d, ctl)[0] if ctl is not None else float("inf")
    except Exception:
        oc = float("inf")
    try:
        s = M._regrow(d, sol, BUDGET, cfg, stay=stay, anchor=(asg, order0))
    except Exception as e:
        print("   stay=%.0f  regrow failed: %s" % (stay, e), flush=True)
        continue
    if s is None:
        print("   stay=%.0f  regrow returned nothing" % stay, flush=True)
        continue
    o, c = SC._total(d, s)
    nb, _ = SC._anchor_of(d, s)
    kept = sum(1 for b in range(n) if nb[b] == asg[b])
    print("   stay=%-7.0f (%4.2f x w3) anchored=%-9d Z1=%-6s Z2=%-6s Z3=%-7s kept %3d/%d |"
          " control=%-9d | anchor %+.2f%%  %s  %.0fs"
          % (stay, mult, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3"), kept, n,
             int(oc) if oc < float("inf") else -1,
             100.0 * (o - oc) / oc if oc < float("inf") else 0.0,
             "BEST" if o < best_o else "", time.time() - t0), flush=True)
    if o < best_o:
        best_o, best_s = o, s

o1, c1 = SC._total(d, best_s)
print("P%d anchored best obj=%-9d Z1=%s Z2=%s Z3=%s feasible=%s  (%+.2f%% vs incumbent)"
      % (PROB, int(o1), c1.get("obj1"), c1.get("obj2"), c1.get("obj3"),
         SC.check_feasibility(d, best_s).get("feasible"), 100.0 * (o1 - o0) / o0), flush=True)

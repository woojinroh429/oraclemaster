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

stay is swept because it decides how much of the anchor survives.  stay = 1 enforces it and
measures whether the packer can realise the optimum at all; lower values let the beam overrule it
where the packing genuinely cannot take it, which is the setting that has to win for this to be
worth shipping.

    python3.12 harness/anchorrun.py PROB BUDGET [MOD] [STAYS]
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
STAYS = [float(x) for x in (sys.argv[4].split(",") if len(sys.argv) > 4 else
                            ["1.0", "0.8", "0.6", "0.3"])]

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
best_o, best_s = o0, sol
for stay in STAYS:
    t0 = time.time()
    try:
        s = M._regrow(d, sol, BUDGET, cfg, stay=stay, anchor=(asg, order0))
    except Exception as e:
        print("   stay=%.2f  regrow failed: %s" % (stay, e), flush=True)
        continue
    if s is None:
        print("   stay=%.2f  regrow returned nothing" % stay, flush=True)
        continue
    o, c = SC._total(d, s)
    nb, _ = SC._anchor_of(d, s)
    kept = sum(1 for b in range(n) if nb[b] == asg[b])
    print("   stay=%-4.2f obj=%-9d Z1=%-6s Z2=%-6s Z3=%-7s  kept %d/%d of the anchor  %s  %.0fs"
          % (stay, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3"), kept, n,
             "BEST" if o < best_o else "", time.time() - t0), flush=True)
    if o < best_o:
        best_o, best_s = o, s

o1, c1 = SC._total(d, best_s)
print("P%d anchored best obj=%-9d Z1=%s Z2=%s Z3=%s feasible=%s  (%+.2f%% vs incumbent)"
      % (PROB, int(o1), c1.get("obj1"), c1.get("obj2"), c1.get("obj3"),
         SC.check_feasibility(d, best_s).get("feasible"), 100.0 * (o1 - o0) / o0), flush=True)

"""Is 97,570 a local optimum on P3, or is a different bay assignment reachable?

Both terms are closed in the neighbourhood of our answer.  Z3: all 24 blocks that missed their
preferred bay are blocked at every tardiness-free entry time, so single-block repair recovers
none of the 543.  Z2: it can be nearly eliminated -- six moves take 3134 to 415 -- but every
preference-neutral move points INTO the overloaded bay, so fixing balance costs preference at
30:1 and the best trade is zero moves.

Meanwhile competitors report 70,000-84,000.  Two closed terms and a large gap is the signature of
a different basin, not of an unexploited local move -- the same shape P6 had, where the answer
was to restart the construction rather than repair it.

The beam can be restarted from a chosen assignment: _regrow re-derives a solution anchored on a
given (bay-per-block, dispatch order) with a stay weight.  So perturb the anchor and regrow.
Three perturbations, because they test different things:

  random    move a fraction of blocks to a uniformly random bay.  Tests whether the basin is
            escapable at all.
  balance   move blocks OUT of the bay with the highest u*load into the lowest, cheapest
            preference first.  The arithmetic says this loses as a pure reassignment; the
            question here is whether letting the beam RE-PACK around it changes that, since the
            re-pack can rescue preference the arithmetic assumed lost.
  pref      move blocks INTO their preferred bay regardless of load.  The 24 blocked blocks
            cannot get there one at a time -- this asks whether they can get there together.

A stay weight below 1 lets the beam overrule the anchor where it strictly helps, so a
perturbation that is simply bad gets undone rather than enforced.
"""
import importlib
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC        # noqa: E402  fixed scorer

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BUDGET = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
KIND = sys.argv[3] if len(sys.argv) > 3 else "random"
FRAC = float(sys.argv[4]) if len(sys.argv) > 4 else 0.15
MOD = sys.argv[5] if len(sys.argv) > 5 else "myalg_base"
SEED = int(sys.argv[6]) if len(sys.argv) > 6 else 777
LIMIT = {3: 240.0, 4: 480.0, 5: 600.0, 6: 900.0}

M = importlib.import_module(MOD)
d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
rng = random.Random(SEED)

sol = M.algorithm(d, LIMIT[PROB] * 0.5)
o0, c0 = SC._total(d, sol)
print("P%d %s start obj=%d Z1=%s Z2=%s Z3=%s"
      % (PROB, MOD, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3")), flush=True)

area = [float(b["width"]) * float(b["height"]) for b in bays]
u = [(sum(area) / m) / area[j] for j in range(m)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
pref = [B[b]["bay_preferences"] for b in range(n)]
want = [max(range(m), key=lambda j: pref[b][j]) for b in range(n)]


def perturb(bay):
    out = list(bay)
    k = max(1, int(FRAC * n))
    if KIND == "pref":
        cand = [b for b in range(n) if out[b] != want[b]]
        for b in rng.sample(cand, min(k, len(cand))):
            out[b] = want[b]
    elif KIND == "balance":
        load = [0.0] * m
        for b in range(n):
            load[out[b]] += wl[b]
        sc = [u[j] * load[j] for j in range(m)]
        src, dst = max(range(m), key=lambda j: sc[j]), min(range(m), key=lambda j: sc[j])
        cand = sorted([b for b in range(n) if out[b] == src],
                      key=lambda b: pref[b][src] - pref[b][dst])
        for b in cand[:k]:
            out[b] = dst
    else:
        for b in rng.sample(range(n), k):
            out[b] = rng.randrange(m)
    return out


best_o, best_s = o0, sol
t0 = time.time()
rounds = 0
cfg = dict(M._AXES[1])
while time.time() - t0 < BUDGET:
    left = BUDGET - (time.time() - t0)
    if left < 30.0:
        break
    ab, ao = SC._anchor_of(d, best_s)
    ab2 = perturb(ab)
    rounds += 1
    try:
        s = M._regrow(d, best_s, min(left, 120.0), cfg, stay=0.6, anchor=(ab2, ao))
    except Exception as e:
        print("   regrow failed: %s" % e, flush=True)
        break
    if s is None:
        continue
    o, c = SC._total(d, s)
    if o < best_o:
        best_o, best_s = o, s
        print("   round %-3d obj=%-10d Z2=%-6s Z3=%-7s  at %.0fs"
              % (rounds, int(o), c.get("obj2"), c.get("obj3"), time.time() - t0), flush=True)
o1, c1 = SC._total(d, best_s)
print("P%d shake=%s frac=%.2f  %d rounds in %.0fs  obj=%-10d Z1=%s Z2=%s Z3=%s  (%+.2f%%)"
      % (PROB, KIND, FRAC, rounds, time.time() - t0, int(o1), c1.get("obj1"), c1.get("obj2"),
         c1.get("obj3"), 100.0 * (o1 - o0) / o0), flush=True)

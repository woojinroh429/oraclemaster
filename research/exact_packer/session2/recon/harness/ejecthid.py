"""Run the ejection chain on the HIDDEN instances, where its retired verdict may not hold.

ejectpipe.py concluded that ejection does not pay, and the reason it gave was arithmetic:

    prize per block   w3*gap / w1  = 1-2 tardiness units
    cost per block    median resident processing - free slack = 7-16 tardiness units

That is the exchange rate on the TRAINING set, and it is decisive there.  It is not the
exchange rate on P3.  P3 has Z1 = 0 with a demand ratio of 0.327 -- a third-full yard with
slack everywhere -- so the disturbance the operator causes need not be paid in tardiness at
all.  Its objective is 78% Z3 and 22% Z2, which is exactly and only what this operator
moves.  The verdict was measured where w1 dominates; P3 is the instance where w1 is inert.

So reuse the machinery verbatim -- it is the validated one: entry and exit times never
change, so Z1 is constant by construction and the accepted delta is the exact
w2*dZ2 + w3*dZ3, with the engine as the sole feasibility authority.  Only the data source
and the seed change: hidden/prob_P.json, seeded and scored by our own build rather than the
deployed one.

Rebinding ejectpipe.M instead of editing it keeps that file exactly as measured.

    python3.12 harness/ejecthid.py PROB SEED_S EJECT_S [K] [T0] [MOD]
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
sys.path.insert(0, REC)
sys.path.insert(0, HERE)

import importlib                 # noqa: E402
import myalg_orig as SC          # noqa: E402  fixed scorer, and the engine/bbox provider
import ejectpipe                 # noqa: E402
ejectpipe.M = SC

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SEED_S = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
EJECT_S = float(sys.argv[3]) if len(sys.argv) > 3 else 300.0
K = int(sys.argv[4]) if len(sys.argv) > 4 else 3
T0 = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
MOD = sys.argv[6] if len(sys.argv) > 6 else "myalg_base"

d = json.load(open(os.path.join(REC, "data/hidden/prob_%d.json" % PROB)))
sol = importlib.import_module(MOD).algorithm(d, SEED_S)
o0, c0 = SC._total(d, sol)
print("P%d %s seed obj=%d Z1=%s Z2=%s Z3=%s"
      % (PROB, MOD, int(o0), c0.get("obj1"), c0.get("obj2"), c0.get("obj3")), flush=True)

ej = ejectpipe.Ejector(d, sol)
print("   %d blocks out of their preferred bay, %d of Z3 conceded"
      % (len(ej.outsiders()), ej.z3()), flush=True)

# WHERE the attempts die.  attempt() returns None both when the move lands but does not pay and
# when it never lands at all, and those two call for opposite conclusions: the first says the
# preference arithmetic is wrong, the second says the bay is geometrically full and the
# concession is forced.  "0 accepted" alone cannot tell them apart -- the same ambiguity that
# made an earlier perturbation experiment unreadable.  Count the bail-out points instead.
TALLY = {"noseat": 0, "novictim": 0, "landed": 0}
DELTAS = []
_fw, _fa = ej._fit_window, ej._fit_any


def _fit_window_c(b, j, victims):
    r = _fw(b, j, victims)
    if r is None:
        TALLY["noseat"] += 1
    return r


def _fit_any_c(c, bays, allow_shift=True):
    r = _fa(c, bays, allow_shift)
    if r is None:
        TALLY["novictim"] += 1
    return r


ej._fit_window, ej._fit_any = _fit_window_c, _fit_any_c
_att = ej.attempt


def _attempt_c(b, victims):
    r = _att(b, victims)
    if r is not None:
        TALLY["landed"] += 1
        DELTAS.append(r[0])
    return r


ej.attempt = _attempt_c

best_s = ej.snapshot()
best_score = ej.score()
cur = best_score
t0 = time.time()

# PHASE 1 -- systematic first-improvement sweep, same split as ejectpipe (35% of the budget).
import itertools                 # noqa: E402
sweep_dl = t0 + EJECT_S * 0.35
improved = True
while improved and time.time() < sweep_dl:
    improved = False
    for b in ej.outsiders():
        if time.time() > sweep_dl:
            break
        j = max(range(ej.m), key=lambda k: ej.pref[b][k])
        pool = ej.victim_pool(b, j)
        hit = False
        for k in range(1, K + 1):
            if hit:
                break
            for combo in itertools.combinations(pool, k):
                r = ej.attempt(b, list(combo))
                if r is None:
                    continue
                delta, tok = r
                if delta < -1e-9:
                    cur += delta
                    ej.accepted += 1
                    improved = True
                    hit = True
                    if cur < best_score - 1e-9:
                        best_score = cur
                        best_s = ej.snapshot()
                    break
                ej.undo(tok)
print("   sweep done at %.0fs: %d accepted of %s attempts, %s scans"
      % (time.time() - t0, ej.accepted, format(ej.attempts, ","), format(ej.scans, ",")),
      flush=True)
print("      outsider never seated in its bay even with the victims gone : %s" % format(TALLY["noseat"], ","))
print("      seated, but a victim had nowhere to go                      : %s" % format(TALLY["novictim"], ","))
print("      landed (whole chain re-seated, delta was computed)          : %s" % format(TALLY["landed"], ","))
if DELTAS:
    DELTAS.sort()
    print("      landed deltas: best %+.0f  median %+.0f  worst %+.0f  (negative = improvement)"
          % (DELTAS[0], DELTAS[len(DELTAS) // 2], DELTAS[-1]), flush=True)

ej.restore(best_s)
cur = best_score
import math                      # noqa: E402
last = time.time()
while time.time() - t0 < EJECT_S:
    r = ej.try_move(K)
    if r is None:
        continue
    delta, tok = r
    frac = 1.0 - (time.time() - t0) / EJECT_S
    T = max(1e-9, T0 * frac * max(1.0, abs(best_score)) * 1e-4)
    if delta < 0 or ej.rng.random() < math.exp(-delta / T):
        cur += delta
        ej.accepted += 1
        if cur < best_score - 1e-9:
            best_score = cur
            best_s = ej.snapshot()
    else:
        ej.undo(tok)
    if time.time() - last > EJECT_S / 4.0:
        ej.restore(best_s)
        cur = best_score
        last = time.time()
ej.restore(best_s)

recs = [{"block_id": b, "bay_id": ej.bay[b], "x": ej.px[b], "y": ej.py[b],
         "orient_idx": ej.ori[b], "entry_time": ej.ent[b], "exit_time": ej.ext[b]}
        for b in range(ej.n)]
s2 = SC._build_operations(recs)
fz = SC.check_feasibility(d, s2)
o2, c2 = SC._total(d, s2)
el = time.time() - t0
print("P%d K=%d eject obj=%-10d Z1=%-6s Z2=%-6s Z3=%-7s feasible=%s  (%+.2f%%)"
      % (PROB, K, int(o2), c2.get("obj1"), c2.get("obj2"), c2.get("obj3"),
         fz.get("feasible"), 100.0 * (o2 - o0) / o0), flush=True)
print("   %s attempts, %s scans, %d accepted in %.0fs (%.0f attempts/s)"
      % (format(ej.attempts, ","), format(ej.scans, ","), ej.accepted, el,
         ej.attempts / max(1e-9, el)), flush=True)

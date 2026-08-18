"""Are the designed dispatch orders locally optimal, or is there a gradient to climb?

This decides whether a BRKGA is worth building, and it needs no BRKGA to answer.

WHAT THE RANDOM-KEY TEST SAID.  brkcorr measured the cheap decoder against the expensive one
over twenty random chromosomes: Spearman rho = +0.220, below the 0.5 bar set before the data
arrived. But it also showed something more useful. A 10 s beam on a RANDOM order returns 136,340
at best over twenty tries, while the pipeline's designed orders reach 96,990 and brk reaches
87,703. Random order space is 55% worse than where we already stand, so a population starting
from random keys spends its budget walking back to the designed orders rather than past them.

THE QUESTION THAT ACTUALLY MATTERS, then, is not "does order matter" -- the same test showed the
beam spanning 136K to 312K across random orders, so it matters enormously -- but:

    is there anything BETTER than edd / lst / defer_big / big_first, near them?

If perturbing a designed order never beats it, the designed orders are local optima, there is no
gradient, and a population search has nothing to find however fast its decoder is. If several
perturbations beat it, there is a gradient and a GA is the tool for climbing it.

HOW IT PERTURBS.  Adjacent-pair swaps at increasing strength, which is the smallest move that
changes a dispatch order at all, applied to the order itself rather than to random keys:

    k = 1, 2, 4, 8, 16, 32 swaps of neighbouring positions

Small k asks whether the order is a strict local optimum; large k asks how far the basin
extends. Every perturbation is scored by the SAME 10 s beam that scores the seed, so the only
thing that differs is the order.

    python3.12 harness/brklocal.py [PROB] [BEAM_SECONDS] [TRIALS_PER_K]
"""
import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
TL = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
TRIALS = int(sys.argv[3]) if len(sys.argv) > 3 else 4

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B = d["blocks"]; bays = d["bays"]; w = d["weights"]
n = len(B); m = len(bays)
due = [int(B[b]["due_date"]) for b in range(n)]
pt = [int(B[b]["processing_time"]) for b in range(n)]
rel = [int(B[b]["release_time"]) for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
pref = [B[b]["bay_preferences"] for b in range(n)]
mxp = [max(p) for p in pref]
bar = [float(q["width"]) * float(q["height"]) for q in bays]
u = [(sum(bar) / m) / bar[j] for j in range(m)]
w1, w2, w3 = float(w["w1"]), float(w["w2"]), float(w["w3"])


def true_obj(flat):
    if not flat or len(flat) % 7:
        return None
    bay = [-1] * n; ext = [-1] * n
    for i in range(0, len(flat), 7):
        b, bb, _o, _x, _y, _en, ex = flat[i:i + 7]
        if 0 <= b < n:
            bay[b] = bb; ext[b] = ex
    if any(v < 0 for v in bay):
        return None
    load = [0.0] * m; z1 = 0.0; z3 = 0.0
    for b in range(n):
        load[bay[b]] += wl[b]
        z1 += max(0, ext[b] - due[b])
        z3 += mxp[b] - pref[b][bay[b]]
    v = [u[j] * load[j] for j in range(m)]
    return w1 * z1 + w2 * math.floor(max(v) - min(v)) + w3 * z3


E = SC._ogc_fast_engine(d)
AR, _bc, _sc = SC._footprint_areas(d)
areas_l = [float(AR[b]) for b in range(n)]
meanp = sum(pt) / n
mu = 1e-3 * min(w1, w3)
_mean_a = sum(AR) / n
_r0 = (max(rel) * 0.2) if rel else 0

# the four orders the pipeline actually ships, built exactly as _contact_beam builds them
ORDERS = {
    "edd":       lambda b: (due[b], AR[b] * 1e-9),
    "lst":       lambda b: (due[b] - pt[b], AR[b] * 1e-9),
    "big_first": lambda b: (1 if AR[b] >= 2.0 * _mean_a else 0, due[b], AR[b] * 1e-9),
    "defer_big": lambda b: (1 if (AR[b] >= 2.0 * _mean_a and rel[b] > _r0) else 0,
                            due[b], -AR[b]),
}


def beam(order):
    E.clear_all()
    _ob, flat = E.contact_beam([int(x) for x in order], areas_l, wl, 96, 4, 1,
                               0.10, 0.0, float(mu), w1, w2, w3, 1.0,
                               float(meanp), float(TL), [], [], float(_sc))
    return true_obj(list(flat))


print("P%d: %d blocks.  beam %.0fs per evaluation, %d trials per perturbation strength"
      % (PROB, n, TL, TRIALS), flush=True)

rng = random.Random(20260801)
summary = []
for name, key in ORDERS.items():
    seed = sorted(range(n), key=key)
    t = time.time()
    base = beam(seed)
    print("\n=== %-10s seed obj = %s   (%.1fs)"
          % (name, ("%d" % base) if base is not None else "incomplete", time.time() - t),
          flush=True)
    if base is None:
        continue
    print("      swaps   trials   best        vs seed    wins")
    for k in (1, 2, 4, 8, 16, 32):
        best, wins = None, 0
        for _ in range(TRIALS):
            o = list(seed)
            for _s in range(k):
                i = rng.randrange(n - 1)
                o[i], o[i + 1] = o[i + 1], o[i]
            v = beam(o)
            if v is None:
                continue
            if best is None or v < best:
                best = v
            if v < base - 1e-9:
                wins += 1
        print("      %5d   %6d   %-10s  %+9s   %d/%d"
              % (k, TRIALS, ("%d" % best) if best is not None else "-",
                 ("%+d" % (best - base)) if best is not None else "-", wins, TRIALS),
              flush=True)
        summary.append((name, k, base, best, wins))

print("\n[VERDICT]")
tot_w = sum(s[4] for s in summary)
tot_t = len(summary) * TRIALS
anybest = [s for s in summary if s[3] is not None and s[3] < s[2]]
print("   %d of %d perturbations beat their own seed" % (tot_w, tot_t))
if anybest:
    b = min(anybest, key=lambda s: s[3] - s[2])
    print("   best improvement: %s at %d swaps, %d -> %d (%+.2f%%)"
          % (b[0], b[1], int(b[2]), int(b[3]), 100.0 * (b[3] - b[2]) / b[2]))
if tot_w == 0:
    print("   -> the designed orders are LOCAL OPTIMA under adjacent swaps.  There is no")
    print("      gradient here, so a population search has nothing to climb however fast its")
    print("      decoder runs.  Do not build the BRKGA.")
elif tot_w <= tot_t * 0.15:
    print("   -> a thin gradient.  Some perturbations win, but rarely enough that a search")
    print("      would spend most of its evaluations on losers -- weak grounds for the build.")
else:
    print("   -> a real gradient: perturbing the designed orders beats them often.  A")
    print("      population search has something to climb, and the 42.7ms decoder makes")
    print("      thousands of climbs affordable.  This is the case for building it.")
print(flush=True)

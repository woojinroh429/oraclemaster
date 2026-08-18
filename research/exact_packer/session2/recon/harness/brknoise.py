"""How much does the beam's answer move when NOTHING moves?

brklocal perturbs a dispatch order and counts how often the perturbation beats its seed. That
count only means something if the beam returns the same number for the same order -- and it does
not. `contact_beam` is given a deadline and adapts its width from measured cost, so two
evaluations of one order differ by however much that adaptation differs.

The evidence that forced this: the same seeded perturbations run twice gave

    8 swaps    aborted run 160,925    rerun 153,250     -- 7,675 apart
    16 swaps   aborted run 163,130    rerun 163,130     -- identical

Some cells reproduce and some do not, which is the signature of a timing-dependent width rather
than of a bug.

So measure the floor directly: evaluate each designed order REPEATEDLY, changing nothing, and
report the spread. Any improvement brklocal attributes to a perturbation has to clear this to
mean anything. If the floor is 12,000 then brklocal's -12,045 at 8 swaps is one draw from the
noise and the order did nothing.

    python3.12 harness/brknoise.py [PROB] [BEAM_SECONDS] [REPEATS]
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
TL = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
REP = int(sys.argv[3]) if len(sys.argv) > 3 else 6

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


print("P%d: the SAME order evaluated %d times, %.0fs beam, nothing changed between runs"
      % (PROB, REP, TL), flush=True)
print("\n   order        values")
floors = []
for name, key in ORDERS.items():
    o = sorted(range(n), key=key)
    vals = []
    for _ in range(REP):
        v = beam(o)
        if v is not None:
            vals.append(int(v))
    if not vals:
        continue
    spread = max(vals) - min(vals)
    floors.append((name, spread, vals))
    print("   %-11s %s" % (name, vals), flush=True)
    print("   %-11s min %d  max %d  SPREAD %d  (%.2f%% of the min)"
          % ("", min(vals), max(vals), spread, 100.0 * spread / min(vals)), flush=True)

print("\n[NOISE FLOOR]")
if floors:
    worst = max(f[1] for f in floors)
    med = sorted(f[1] for f in floors)[len(floors) // 2]
    print("   median spread across the four orders: %d" % med)
    print("   worst: %d (%s)" % (worst, max(floors, key=lambda f: f[1])[0]))
    print("\n   brklocal's best perturbation gains, for comparison:")
    print("      edd  8 swaps   -12,045")
    print("      edd 32 swaps   -15,085")
    print("\n   -> %s"
          % ("those gains are INSIDE the noise floor, so brklocal measured the beam's own"
             " variability and not the effect of reordering.  The perturbation test has to be"
             " rebuilt around repeated evaluation before it can decide anything."
             if med >= 12000 else
             "the gains clear the floor, so reordering is doing something the beam's own"
             " variability does not explain -- brklocal's counts can be read, with the floor"
             " subtracted."), flush=True)

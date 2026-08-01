"""Does the cheap decoder RANK dispatch orders the way the expensive one does?

This is the whole build/no-build decision for a BRKGA over orders, and it is the exact question
that sank the last attempt.

WHERE IT STANDS.  `ogc_fast.Engine.greedy_rollout` decodes an order in 42.7 ms -- 180x faster
than the `st3dtcs.st_best` decoder that made BRKGA useless before (5-7 s, about two generations
in a 15 s budget). At that speed a 240 s run affords 5,625 decodes single-core, which is a real
population search. And the objective does move with the chromosome: sixteen random ones gave
sixteen distinct values.

WHY THAT IS NOT ENOUGH.  Those values sit near 1,000,000, against 96,990 for our base and 87,703
for brk. greedy_rollout is the beam's fast approximate rollout for ranking STATES, not a solver;
it trades quality for speed. That does not disqualify it -- a BRKGA would only use it to CHOOSE
among orders and realise the winner through the expensive path -- but it makes everything depend
on one thing:

    does the cheap decoder's ORDERING of chromosomes match the expensive path's?

If it does, searching 5,000 cheap decodes finds orders the expensive path will also like, and
the absolute scale of the cheap number is irrelevant. If it does not, the search picks wrong
orders quickly, which is precisely what the Extreme-Point decoder did -- 9-12x faster, 2.8-3.3x
worse, and 13-21 of its generations still lost to 2 grid generations.

WHAT THIS MEASURES.  The same chromosome down both paths:

    cheap       E.greedy_rollout(prio)          -> flat assignment -> true objective
    expensive   E.contact_beam(order, ...)      -> flat assignment -> true objective

`contact_beam` takes the dispatch order as an explicit list, so both paths get exactly the same
order and nothing else differs. Spearman rank correlation over N chromosomes, plus the check
that actually matters for a GA: of the chromosomes the cheap path ranks best, how many are
genuinely good under the expensive one.

    rho >= 0.5    build it -- cheap search finds orders the expensive path agrees with
    rho ~ 0       do not build -- 5,000 decodes would pick wrong orders quickly
    rho < 0       the cheap decoder is actively misleading

    python3.12 harness/brkcorr.py [PROB] [N] [BEAM_SECONDS]
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
N = int(sys.argv[2]) if len(sys.argv) > 2 else 24
TL = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B = d["blocks"]; bays = d["bays"]; w = d["weights"]
n = len(B); m = len(bays)
due = [int(B[b]["due_date"]) for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
pref = [B[b]["bay_preferences"] for b in range(n)]
mxp = [max(p) for p in pref]
bar = [float(q["width"]) * float(q["height"]) for q in bays]
u = [(sum(bar) / m) / bar[j] for j in range(m)]
w1, w2, w3 = float(w["w1"]), float(w["w2"]), float(w["w3"])
import math


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
meanp = sum(int(B[b]["processing_time"]) for b in range(n)) / n
mu = 1e-3 * min(w1, w3)

print("P%d: %d blocks, %d bays.  %d chromosomes, beam budget %.0fs each"
      % (PROB, n, m, N, TL), flush=True)
print("\n   k    cheap(ms)      cheap obj    beam(s)       beam obj")

rng = random.Random(20260801)
pairs = []
for k in range(N):
    prio = ([float(due[b]) for b in range(n)] if k == 0
            else [rng.random() for _ in range(n)])
    order = sorted(range(n), key=lambda b: (prio[b], b))

    E.clear_all()
    t = time.time()
    _s, flat = E.greedy_rollout([float(x) for x in prio], 0, 1, True, n, False)
    tc = time.time() - t
    oc = true_obj(list(flat))

    E.clear_all()
    t = time.time()
    try:
        _ob, bflat = E.contact_beam([int(x) for x in order], areas_l, wl, 96, 4, 1,
                                    0.10, 0.0, float(mu), w1, w2, w3, 1.0,
                                    float(meanp), float(TL), [], [], float(_sc))
    except Exception as e:
        print("   contact_beam call failed: %s" % e)
        sys.exit(1)
    tb = time.time() - t
    ob = true_obj(list(bflat))

    if oc is None or ob is None:
        print("   %2d   %8.1f   %12s   %7.1f   %12s   (incomplete, skipped)"
              % (k, tc * 1000, oc, tb, ob), flush=True)
        continue
    pairs.append((oc, ob))
    print("   %2d   %8.1f   %12d   %7.1f   %12d" % (k, tc * 1000, int(oc), tb, int(ob)),
          flush=True)

if len(pairs) < 5:
    print("\n   too few complete pairs to judge")
    sys.exit(0)


def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    for pos, i in enumerate(order):
        r[i] = float(pos)
    return r


ca = [p[0] for p in pairs]; ba = [p[1] for p in pairs]
rc, rb = rank(ca), rank(ba)
mc = sum(rc) / len(rc); mb = sum(rb) / len(rb)
num = sum((rc[i] - mc) * (rb[i] - mb) for i in range(len(rc)))
den = (sum((x - mc) ** 2 for x in rc) * sum((x - mb) ** 2 for x in rb)) ** 0.5
rho = num / den if den else 0.0

print("\n[CORRELATION]  Spearman rho = %+.3f over %d chromosomes" % (rho, len(pairs)))
print("   cheap    best %d  worst %d" % (int(min(ca)), int(max(ca))))
print("   beam     best %d  worst %d" % (int(min(ba)), int(max(ba))))

# The question a GA actually asks: if I keep the top fifth by the cheap score, have I kept
# orders the expensive path also likes?
k = max(1, len(pairs) // 5)
top_cheap = sorted(range(len(pairs)), key=lambda i: ca[i])[:k]
best_beam = sorted(range(len(pairs)), key=lambda i: ba[i])[:k]
hit = len(set(top_cheap) & set(best_beam))
print("   of the %d chromosomes the cheap decoder ranks best, %d are also in the beam's best %d"
      % (k, hit, k))
print("   beam objective of the cheap-best: %d    beam's own best: %d    median: %d"
      % (int(min(ba[i] for i in top_cheap)), int(min(ba)),
         int(sorted(ba)[len(ba) // 2])))

if rho >= 0.5:
    v = ("BUILD IT.  The cheap decoder agrees with the expensive one about which orders are"
         " good, so 5,000 cheap decodes are 5,000 useful decodes and the absolute scale of the"
         " cheap number does not matter.")
elif rho > 0.15:
    v = ("WEAK.  There is signal but not much; a population would spend most of its budget on"
         " orders the expensive path does not rate, which is how the Extreme-Point decoder"
         " failed.")
elif rho > -0.15:
    v = ("DO NOT BUILD.  The cheap ranking is uninformative about the expensive one -- 5,000"
         " decodes would pick wrong orders quickly, which is exactly the previous failure.")
else:
    v = ("DO NOT BUILD, and note the sign: the cheap decoder is actively ANTI-correlated, so"
         " selecting on it would steer the search away from good orders.")
print("   -> %s" % v, flush=True)

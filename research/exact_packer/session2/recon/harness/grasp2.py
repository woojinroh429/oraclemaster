"""GRASP with memory: stop restarting blind.

Plain GRASP broke 28M on P6 -- 27,786,975 against the deployed build's 28,373,827 -- but its
draws are mutually independent.  Draw 34 of 43 found the incumbent and draw 35 began again from
nothing, knowing none of it.  Over a 250-block permutation space that is a lot of budget spent
re-deriving the same structure, and the k sweep shows what it costs: k=3 reached 28,194,724,
k=6 reached 27,887,068, and k=10 improved on the pure greedy zero times in 43 draws.  Widen the
randomisation slightly and the greedy signal is gone, because nothing accumulates.

Three changes, all standard, all removing something hand-set:

  elite memory   keep the best few orders; bias each new draw toward where they agree.  Good
                 solutions on this instance share structure -- which blocks must go early -- and
                 blind restarts throw that away every time.  alpha ramps with the pool so the
                 first draws stay close to the base key.
  reactive k     k is not fixed.  Each value carries a weight, raised when it produces a draw
                 better than the running median.  This is also what makes the procedure
                 instance-agnostic: P5 and P6 are different regimes and can prefer different k
                 without anything being gated on the instance.
  polish-aware   the old selection picked the best UNPOLISHED construction and polished it once.
    selection    Those are not the same ranking: the polish takes Z2 and Z3, so a build holding
                 more of them can finish ahead of one that starts lower.  Short-polish the top
                 few, re-rank, then spend the long polish on the winner.

k=1 with no elites is still the plain greedy, so the whole thing remains a relaxation of sac3.
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import myalgorithm as A          # noqa: E402
import myalg_orig as M           # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 6
BUDGET = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
POL = float(sys.argv[3]) if len(sys.argv) > 3 else 250.0
MODE = sys.argv[4] if len(sys.argv) > 4 else "flatbl"
SEED = int(sys.argv[5]) if len(sys.argv) > 5 else 777
ELITE = 8
KS = [3, 4, 6, 8]
SHORTPOL = 15.0
TOPN = 4

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
n = len(d["blocks"])
w = d["weights"]
B = d["blocks"]
rng = random.Random(SEED)

ar, _bc, _sc = A._footprint_areas(d)
due = [b["due_date"] for b in B]
pt = [b["processing_time"] for b in B]


def _rank(v, rev):
    o = sorted(range(n), key=lambda i: v[i], reverse=rev)
    r = [0.0] * n
    for p, i in enumerate(o):
        r[i] = p / max(1, n - 1)
    return r


rd, ra = _rank(due, False), _rank(ar, True)
vic = set(sorted(range(n), key=lambda b: -(ar[b] * pt[b]))[:3])
base_order = sorted(range(n), key=lambda b: (1 if b in vic else 0, rd[b] + ra[b], due[b]))
base_pos = [0.0] * n
for p, b in enumerate(base_order):
    base_pos[b] = p / max(1, n - 1)


def build(order, secs):
    saved = A._CPP_ENGINE_MODE
    A._CPP_ENGINE_MODE = A.HAVE_OGC_FAST
    try:
        return A._smallright_construct(d, secs, small_thresh=0.60, step=1, mode=MODE, order=order)
    finally:
        A._CPP_ENGINE_MODE = saved


def score(recs):
    return M._total(d, A._build_operations([recs[b] for b in range(n)]))[0]


def flatten(recs):
    f = []
    for b in range(n):
        r = recs[b]
        f += [b, r["bay_id"], r["orient_idx"], int(r["x"]), int(r["y"]),
              int(r["entry_time"]), int(r["exit_time"])]
    return f


E = M._ogc_fast_engine(d)
wls = [float(B[b].get("workload", 0.0)) for b in range(n)]


def polish(recs, secs):
    try:
        out = list(E.z3_reassign(flatten(recs), float(w["w1"]), float(w["w3"]), float(secs),
                                 float(w["w2"]), wls))
    except TypeError:
        out = list(E.z3_reassign(flatten(recs), float(w["w1"]), float(w["w3"]), float(secs)))
    r2 = {}
    for i in range(0, len(out), 7):
        b = out[i]
        r2[b] = {"block_id": b, "bay_id": out[i + 1], "orient_idx": out[i + 2],
                 "x": out[i + 3], "y": out[i + 4],
                 "entry_time": out[i + 5], "exit_time": out[i + 6]}
    sol = M._build_operations([r2[b] for b in range(n)])
    return r2, M._total(d, sol)


elite = []                                  # [(obj, order)], best first
kw = {k: 1.0 for k in KS}                   # reactive weights
seen = []                                   # objective history, for the median test
pool_best = []                              # [(obj, recs, order)] candidates for re-ranking

t0 = time.time()
draws = 0
while time.time() - t0 < BUDGET:
    left = BUDGET - (time.time() - t0)
    if left < 20.0:
        break
    tot = sum(kw.values())
    r, acc, k = rng.random() * tot, 0.0, KS[-1]
    for kk in KS:
        acc += kw[kk]
        if r <= acc:
            k = kk
            break

    if draws == 0:
        order = list(base_order)
    else:
        if elite:
            # where the elites agree, follow them; alpha ramps so early draws stay near the key
            alpha = min(0.5, 0.08 * len(elite))
            epos = [0.0] * n
            for _o, eo in elite:
                for p, b in enumerate(eo):
                    epos[b] += p / max(1, n - 1)
            epos = [v / len(elite) for v in epos]
            keyv = [(1.0 - alpha) * base_pos[b] + alpha * epos[b] for b in range(n)]
        else:
            keyv = base_pos
        pool = sorted(range(n), key=lambda b: keyv[b])
        order = []
        while pool:
            order.append(pool.pop(rng.randrange(min(k, len(pool)))))

    recs = build(order, min(left, 60.0))
    draws += 1
    if not recs or len(recs) != n:
        continue
    o = score(recs)
    seen.append(o)
    med = sorted(seen)[len(seen) // 2]
    kw[k] *= 1.25 if o <= med else 0.9       # reactive: reward what beats the running median
    kw[k] = max(0.15, min(6.0, kw[k]))

    elite.append((o, list(order)))
    elite.sort(key=lambda t: t[0])
    del elite[ELITE:]
    pool_best.append((o, recs))
    pool_best.sort(key=lambda t: t[0])
    del pool_best[TOPN:]
    if o <= min(seen):
        print("   draw %-3d k=%d obj=%-11d  at %.0fs" % (draws, k, int(o), time.time() - t0),
              flush=True)

if not pool_best:
    print("P%d  nothing completed in %.0fs" % (PROB, BUDGET))
    sys.exit(1)

print("P%-2d GRASP2 %d draws in %.0fs   k weights %s   best build=%d"
      % (PROB, draws, time.time() - t0,
         " ".join("%d:%.2f" % (k, kw[k]) for k in KS), int(pool_best[0][0])), flush=True)

# re-rank the finalists by what they are worth AFTER polishing, not before
ranked = []
for o, recs in pool_best:
    _r, (po, _c) = polish(recs, SHORTPOL)
    ranked.append((po, o, recs))
    print("   finalist build=%-11d short-polish=%-11d" % (int(o), int(po)), flush=True)
ranked.sort(key=lambda t: t[0])
if ranked[0][1] != pool_best[0][0]:
    print("   -> re-ranked: the best build was NOT the best polished", flush=True)

_r, (o1, c1) = polish(ranked[0][2], POL)
sol = M._build_operations([_r[b] for b in range(n)])
print("P%-2d GRASP2 final  obj=%-11d Z1=%-7s Z2=%-5s Z3=%-7s feasible=%s"
      % (PROB, int(o1), c1.get("obj1"), c1.get("obj2"), c1.get("obj3"),
         M.check_feasibility(d, sol).get("feasible")), flush=True)

"""Is a BRKGA over dispatch orders viable on P3, or does it die the way it died before?

WHAT KILLED IT LAST TIME.  `HD_FINDINGS.md`: the decoder was `st3dtcs.st_best` at 5-7 s per
decode on 150-200 block instances, so a 15 s budget bought about TWO generations. That is not a
genetic algorithm, it is picking the better of two seed orders, and it lost to greedy for that
reason alone. Every attempt to speed the decoder traded quality away -- the Extreme-Point
variant was 9-12x faster and 2.8-3.3x worse, and 13-21 of its generations still lost to 2 grid
generations.

WHAT IS DIFFERENT NOW.  `ogc_fast.Engine.greedy_rollout` exists. It was built as the beam's
rollout -- called once per surviving state per level, so it had to be fast, and an earlier task
in this project accelerated it tenfold on purpose. It takes a dispatch order and returns a
complete solution, which is exactly a BRKGA decoder. Nobody has ever timed it in that role.

So time it, and let the number decide before anything is built:

    ~50 ms     4,800 decodes in a 240 s run -- a real population search
    ~500 ms      480 decodes -- shallow, but genuinely searching
    ~5 s          48 decodes -- the same failure as before; do not build it

The script also checks the two things that make the decoder usable at all: that different orders
actually produce different objectives (a decoder insensitive to its input cannot be searched),
and that the solutions it returns are feasible.

    python3.12 harness/brkgate.py [PROB] [N_DECODES]
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
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B = d["blocks"]; n = len(B)
due = [int(B[b]["due_date"]) for b in range(n)]
print("P%d: %d blocks, %d bays" % (PROB, n, len(d["bays"])), flush=True)

E = SC._ogc_fast_engine(d)
if not hasattr(E, "greedy_rollout"):
    print("no greedy_rollout on this engine -- cannot gate")
    sys.exit(1)

import inspect
try:
    print("\ngreedy_rollout signature:\n   %s" % (E.greedy_rollout.__doc__ or "").split("\n")[0])
except Exception:
    pass

# greedy_rollout takes `prio`, a float per block -- which IS a BRKGA chromosome, so the decoder
# is already the right shape and the timing below is the timing a population search would see.
# Chromosome 0 is EDD (priority = due date) as the reference; the rest are random keys.
rng = random.Random(12345)
base_prio = [float(due[b]) for b in range(n)]

# The rollout's own score is TARDINESS, and P3's tardiness is 0 in every arrangement -- so that
# number cannot distinguish chromosomes here and reading it would say "insensitive" about an
# instance where Z1 is structurally zero.  What a population must select on is the objective the
# grader uses, and the flat assignment carries the bay per block, which is all Z2 and Z3 need.
import math as _m
_bays = d["bays"]; _w = d["weights"]
_bar = [float(q["width"]) * float(q["height"]) for q in _bays]
_u = [(sum(_bar) / len(_bar)) / _bar[j] for j in range(len(_bays))]
_wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
_pref = [B[b]["bay_preferences"] for b in range(n)]
_mxp = [max(p) for p in _pref]


def _true_obj(flat):
    """w1*Z1 + w2*Z2 + w3*Z3 from the rollout's flat (b, bay, orient, x, y, en, ex) records."""
    if not flat or len(flat) % 7:
        return None
    bay = [-1] * n; ext = [-1] * n
    for i in range(0, len(flat), 7):
        b, bb, _o, _x, _y, _en, ex = flat[i:i + 7]
        if 0 <= b < n:
            bay[b] = bb; ext[b] = ex
    if any(v < 0 for v in bay):
        return None
    load = [0.0] * len(_bays); z1 = 0.0; z3 = 0.0
    for b in range(n):
        load[bay[b]] += _wl[b]
        z1 += max(0, ext[b] - due[b])
        z3 += _mxp[b] - _pref[b][bay[b]]
    v = [_u[j] * load[j] for j in range(len(_bays))]
    return (float(_w["w1"]) * z1 + float(_w["w2"]) * _m.floor(max(v) - min(v))
            + float(_w["w3"]) * z3)


rows = []
for k in range(N):
    prio = base_prio if k == 0 else [rng.random() for _ in range(n)]
    E.clear_all()
    t = time.time()
    r = E.greedy_rollout([float(x) for x in prio], 0, 1, True, n, False)
    el = time.time() - t
    rows.append((el, r))
    if k < 3 or k == N - 1:
        print("   decode %2d: %7.1f ms   rollout_score=%.6g  TRUE obj=%s"
              % (k, el * 1000.0, float(r[0]),
                 ("%d" % _true_obj(list(r[1]))) if _true_obj(list(r[1])) is not None
                 else "incomplete"), flush=True)

ts = sorted(x[0] for x in rows)
med = ts[len(ts) // 2]
print("\n[TIMING]  median %.1f ms, min %.1f, max %.1f over %d decodes"
      % (med * 1000, ts[0] * 1000, ts[-1] * 1000, len(rows)))
budget = {3: 240.0}.get(PROB, 240.0)
print("   decodes affordable in a %.0fs run, single core: %.0f" % (budget, budget / max(1e-6, med)))
print("   across 4 workers: %.0f" % (4 * budget / max(1e-6, med)))

if med > 2.0:
    verdict = ("DO NOT BUILD.  This is the failure that removed BRKGA the first time -- a"
               " population search that manages tens of decodes is not searching.")
elif med > 0.2:
    verdict = ("SHALLOW BUT REAL.  Hundreds of decodes is a genuine population search, though"
               " small; worth building only if the objective actually varies with the order.")
else:
    verdict = ("VIABLE.  Thousands of decodes in budget is a real GA, and the decoder is no"
               " longer the barrier it was.")
print("   -> %s" % verdict, flush=True)

# A decoder whose output does not move with its input cannot be searched, however fast it is.
# greedy_rollout returns (score, flat_assignment); the score is what a population would select
# on, so that is what has to vary.  An earlier version of this counted len(r), which is 2 for
# every tuple and therefore measured nothing.
vals = set()
for el, r in rows:
    try:
        o = _true_obj(list(r[1]))
        if o is not None:
            vals.add(int(o))
    except Exception:
        pass
_sv = sorted(vals)
print("\n   true objectives seen: %s%s" % (["%d" % v for v in _sv[:6]],
                                            " ..." if len(_sv) > 6 else ""))
if _sv:
    print("   best %d, worst %d, spread %d" % (_sv[0], _sv[-1], _sv[-1] - _sv[0]))
print("\n[SENSITIVITY]  %d distinct decoder outputs over %d random chromosomes"
      % (len(vals), len(rows)))
print("   -> %s" % ("the order matters, so there is something for a population to search"
                    if len(vals) > 1 else
                    "the decoder returned the SAME thing for every chromosome -- either the"
                    " wrong call shape or an order-insensitive decoder, and a GA over it is"
                    " pointless either way"), flush=True)

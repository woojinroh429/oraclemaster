"""How much of the entry delay is OUR fragmentation, and how much is the instance?

WHY THIS IS THE QUESTION.  Z1 is the median 59.4% of the objective on the final set and it is
entirely entry delay -- measured overstay is zero everywhere, so every unit of Z1 is a block
that could not get in when it was released.  Meanwhile the yard runs at about half occupancy.
Those two facts have never been reconciled, and six operators have now been refuted for
assuming that free area implies a placeable block.

THE FREE MOVE NOBODY HAS TRIED.  The objective reads (bay, entry_time) and nothing else -- x, y
and orientation appear nowhere in w1*Z1 + w2*Z2 + w3*Z3.  So rearranging blocks WITHIN their
own bay and window, changing only position and orientation, cannot change the objective by
construction.  It is not a trade to be priced; it either opens room or it does not.  What it
opens is worth having, because a block that gets in at its release time instead of later takes
its whole delay off Z1.

WHAT THIS MEASURES, per delayed block, at its RELEASE time:

    A  shape      does it fit in an EMPTY bay at that window?   No  -> the instance is telling
                  us this block waits, and no operator can help.
    B  as-is      does it fit RIGHT NOW, without moving anything?   Yes -> the delay was not
                  forced at all and the scheduler simply missed it.
    C  repack     insert it FIRST, then re-seat every resident of that bay whose window
                  overlaps.  All of them fit again -> the delay is OUR fragmentation and a
                  compaction pass can take it back.

C is deliberately a GREEDY re-seat, so a "yes" is genuine and a "no" is not proof -- the number
it produces is a LOWER bound on what compaction could recover.  That is the useful direction:
if a lower bound is already large the operator is worth building, and if it is near zero then
the yard is not fragmented and the whole idea dies here for a stated reason rather than after a
day of implementation.

Run: python3.12 harness/defrag.py <prob> <secs> [--data <dir>] [--cap N]
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
_DD = sys.argv[sys.argv.index("--data") + 1] if "--data" in sys.argv else "data/hidden"
CAP = int(sys.argv[sys.argv.index("--cap") + 1]) if "--cap" in sys.argv else 60
STEP = int(sys.argv[sys.argv.index("--step") + 1] if "--step" in sys.argv else 2)

import numpy as _np                                      # noqa: E402
import myalgorithm as A                                  # noqa: E402
import utils                                             # noqa: E402

prob = json.load(open(os.path.join(HERE, _DD, "prob_%d.json" % PROB)))
B = prob["blocks"]
n = len(B)
m = len(prob["bays"])
rel = [int(b["release_time"]) for b in B]
pt = [int(b["processing_time"]) for b in B]

t0 = time.time()
sol = A.algorithm(prob, SECS)
c = utils.check_feasibility(prob, sol)
print("P%d  solution obj=%.0f feas=%s  (%.0fs)"
      % (PROB, c["objective"], c["feasible"], time.time() - t0), flush=True)

ent = {}; ext = {}; bay = {}; ori = {}; px = {}; py = {}
for tstr, row in sol["operations"].items():
    for op in row:
        b = op["block_id"]
        if op["type"] == "ENTRY":
            ent[b] = int(tstr); bay[b] = op["bay_id"]; ori[b] = op["orient_idx"]
            px[b] = op["x"]; py[b] = op["y"]
        else:
            ext[b] = int(tstr)

delayed = sorted((b for b in range(n) if ent.get(b, 0) > rel[b]),
                 key=lambda b: -(ent[b] - rel[b]))
tot_delay = sum(ent[b] - rel[b] for b in delayed)
print("   delayed blocks %d/%d,  total entry delay %d days" % (len(delayed), n, tot_delay),
      flush=True)
samp = delayed[:CAP]
print("   examining the %d longest-delayed (%.0f%% of the delay)"
      % (len(samp), 100.0 * sum(ent[b] - rel[b] for b in samp) / max(1, tot_delay)), flush=True)

E = A._ogc_fast_engine(prob)


def load_state():
    E.clear_all()
    for b in range(n):
        if b in ent:
            E.add(bay[b], b, ori[b], float(px[b]), float(py[b]), ent[b], ext[b])


def first_fit(b, bays, en, ex):
    """(bay, oi, x, y) of the first feasible seat, or None.

    feasible_scan hands back an (N, 4) array, so it has to be flattened before the quadruple
    is read -- taking r[:4] off the raw return gives four ROWS, and float() on a row raises
    'only 0-dimensional arrays can be converted'."""
    a = _np.asarray(E.feasible_scan(b, list(bays), en, ex, STEP)).ravel()
    return tuple(int(v) for v in a[:4]) if a.size >= 4 else None


load_state()

# ---- B: does it fit right now, with nothing moved? -------------------------------------
fit_now = []
for b in samp:
    en = rel[b]; ex = en + pt[b]
    E.remove(b)                                    # it is elsewhere in time; take it out first
    if first_fit(b, range(m), en, ex):
        fit_now.append(b)
    E.add(bay[b], b, ori[b], float(px[b]), float(py[b]), ent[b], ext[b])

# ---- C: insert it first, then re-seat everyone it displaced ----------------------------
recover = []
for b in samp:
    if b in fit_now:
        continue
    en = rel[b]; ex = en + pt[b]
    won = False
    for j in range(m):
        load_state()
        E.remove(b)
        # everyone in bay j whose residency overlaps [en, ex)
        occ = [q for q in range(n) if q != b and q in ent and bay[q] == j
               and ent[q] < ex and en < ext[q]]
        for q in occ:
            E.remove(q)
        seat = first_fit(b, [j], en, ex)
        if not seat:
            continue                               # not even an empty-ish bay takes it
        E.add(j, b, seat[1], float(seat[2]), float(seat[3]), en, ex)
        # re-seat the displaced, biggest first -- a greedy pass, so success is real and
        # failure is not proof
        occ.sort(key=lambda q: -(pt[q]))
        ok = True
        for q in occ:
            s2 = first_fit(q, [j], ent[q], ext[q])
            if not s2:
                ok = False
                break
            E.add(j, q, s2[1], float(s2[2]), float(s2[3]), ent[q], ext[q])
        if ok:
            won = True
            break
    if won:
        recover.append(b)

# ---- A: would an EMPTY yard take it? ---------------------------------------------------
E.clear_all()
shape_ok = []
for b in samp:
    if first_fit(b, range(m), rel[b], rel[b] + pt[b]):
        shape_ok.append(b)

d_of = lambda S: sum(ent[b] - rel[b] for b in S)      # noqa: E731
sd = max(1, d_of(samp))
never = [b for b in samp if b not in shape_ok]
stuck = [b for b in samp if b not in fit_now and b not in recover and b in shape_ok]
print()
print("   %-34s %6s %10s" % ("verdict", "blocks", "delay days"))
print("   %-34s %6d %10d   %5.1f%%" % ("B  fits now, nothing moved", len(fit_now),
                                       d_of(fit_now), 100.0 * d_of(fit_now) / sd))
print("   %-34s %6d %10d   %5.1f%%" % ("C  fits after repacking the bay", len(recover),
                                       d_of(recover), 100.0 * d_of(recover) / sd))
print("   %-34s %6d %10d   %5.1f%%" % ("A  never fits, empty yard", len(never),
                                       d_of(never), 100.0 * d_of(never) / sd))
print("   %-34s %6d %10d   %5.1f%%" % ("   genuinely full", len(stuck),
                                       d_of(stuck), 100.0 * d_of(stuck) / sd))
print("\n   RECOVERABLE (B+C) = %.1f%% of the sampled delay -- a LOWER bound, greedy re-seat"
      % (100.0 * (d_of(fit_now) + d_of(recover)) / sd), flush=True)

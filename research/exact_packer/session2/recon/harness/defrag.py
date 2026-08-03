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

# SAMPLING.  Taking the longest-delayed first selects the blocks the yard refused for the
# longest, which is the most adversarial sample there is -- a 0% off those says little about the
# typical delayed block.  --pick random draws uniformly from all of them instead.
PICK = sys.argv[sys.argv.index("--pick") + 1] if "--pick" in sys.argv else "long"
if PICK == "random":
    import random as _rnd
    samp = _rnd.Random(20260803).sample(delayed, min(CAP, len(delayed)))
else:
    samp = delayed[:CAP]
print("   examining %d blocks, %s (%.0f%% of the delay)"
      % (len(samp), "drawn uniformly" if PICK == "random" else "the longest-delayed",
         100.0 * sum(ent[b] - rel[b] for b in samp) / max(1, tot_delay)), flush=True)

# HOW FULL IS THE YARD AT THE MOMENTS THAT DECIDE?  "The yard runs at 53.7%" is an average over
# time, and admission is decided by the busiest instant of the block's own window.  If those two
# numbers are far apart then the yard was never half empty when it mattered, and the whole
# fragmentation story is answered before any packing is attempted.
_AR, _bc, _sc = A._footprint_areas(prob)
occ_at = []
for b in samp:
    en = rel[b]; ex = en + pt[b]
    best = 0.0
    for j in range(m):
        area = float(prob["bays"][j]["width"]) * float(prob["bays"][j]["height"])
        peak = 0.0
        for t in range(en, max(en + 1, ex)):
            u = sum(_AR[q] for q in range(n) if q in ent and bay[q] == j
                    and ent[q] <= t < ext[q])
            peak = max(peak, u)
        best = max(best, 0.0) if area <= 0 else max(best, 1.0 - peak / area)
    occ_at.append(best)
print("   free area in the emptiest bay over the block's own window: median %.1f%%, max %.1f%%"
      % (100.0 * sorted(occ_at)[len(occ_at) // 2], 100.0 * max(occ_at)), flush=True)

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

# ---- C: can an EXACT packer seat the block plus everyone whose window it shares? --------
#
# The first version of this re-seated the displaced residents by first fit, and it returned 0
# of 40 with every block landing in the same bucket -- which is the shape of a broken test, not
# of a measurement.  Emptying a bay of dozens of residents and re-inserting them at the first
# feasible cell is a far worse packer than whatever produced the arrangement in the first
# place, so a failure said nothing about the yard.
#
# cranepack is the exact set-packing solver bayrepack already uses: give it the blocks with
# their windows and it seats the maximum-weight subset that respects the crane rule.  If IT
# cannot seat everyone, "cannot" finally means something.
#
# THE GRID THE PACKER GETS IS NOT THE GRID THE SCAN GETS.  The first run with cranepack asked
# nothing at all: prob_2 puts 250 blocks in 3 bays, so a window is shared by far more than the
# 24 residents the cap allowed, and all 120 possible bay-tests were skipped.  "100% genuinely
# full" was the default, not a measurement -- which is what the skip counter exists to catch.
#
# Raising the cap alone does not work, because cranepack's build is O(ncol^2): at the scan's
# step, forty blocks generate ~50k columns and the build alone runs for tens of minutes.  brk
# uses step 4-6 with a tier ladder for exactly this reason.  So the packer gets its own, coarser
# step while the scan keeps its resolution.  A coarse grid can miss a seat a fine one would
# find, so this still under-reports -- which is the honest direction: a "yes" is real.
import bayrepack as _R                                     # noqa: E402
CP = _R._load()
CAPQ = int(sys.argv[sys.argv.index("--capq") + 1] if "--capq" in sys.argv else 48)
PACKS = float(sys.argv[sys.argv.index("--packs") + 1] if "--packs" in sys.argv else 10.0)
PSTEP = int(sys.argv[sys.argv.index("--pstep") + 1] if "--pstep" in sys.argv else 6)

recover = []
packed_fail = 0
for b in samp:
    if b in fit_now:
        continue
    en = rel[b]; ex = en + pt[b]
    won = False
    for j in range(m):
        occ = [q for q in range(n) if q != b and q in ent and bay[q] == j
               and ent[q] < ex and en < ext[q]]
        # a window shared with more than CAPQ residents makes the column count explode; those
        # are counted separately rather than silently called infeasible
        if len(occ) > CAPQ:
            packed_fail += 1
            continue
        cand = [b] + occ
        blocks_in = [(_R._layers_bbox(B, q)[0], _R._layers_bbox(B, q)[1],
                      [(en, ex)] if q == b else [(ent[q], ext[q])]) for q in cand]
        W = float(prob["bays"][j]["width"]); H = float(prob["bays"][j]["height"])
        try:
            r = CP.pack(blocks_in, W, H, PSTEP, PACKS, seed=1, warm=None, frozen=[],
                        weights=[1.0] * len(cand), total_s=PACKS * 3.0)
        except Exception:
            continue
        if len(r) > 9 and int(r[9]) == 1:      # build aborted -> no verdict from this bay
            packed_fail += 1
            continue
        # r[1] is the seating: (column index, orient, x, y, entry, exit) per seated block.
        # Index 0 is the waiting block, so it has to be among them AND nobody may be dropped --
        # a repack that admits b by evicting a resident is not free and is not what this counts.
        got = {int(loc) for (loc, _o, _x, _y, _e, _x2) in r[1]}
        if len(got) == len(cand) and 0 in got:
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
print("\n   RECOVERABLE (B+C) = %.1f%% of the sampled delay -- still a LOWER bound: cranepack is"
      % (100.0 * (d_of(fit_now) + d_of(recover)) / sd))
print("   cranepack got %.0fs per bay on a step-%d grid; %d of %d bay-tests could not be asked"
      " (>%d window-sharers, or the build aborted)"
      % (PACKS, PSTEP, packed_fail, len([b for b in samp if b not in fit_now]) * m, CAPQ),
      flush=True)

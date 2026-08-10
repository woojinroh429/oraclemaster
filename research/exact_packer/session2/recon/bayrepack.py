"""Repack the contested bay exactly, instead of nudging one block at a time.

WHY THIS OPERATOR EXISTS.  On P3 the capacity-aware lower bound is 36,765 and the best result
anything has produced is 87,560 -- 138% above it -- and the bound is not blocked by area: bay
0's first-choice demand is 0.48 of its cells x horizon.  What separates the two is packing
efficiency under the crane rule.  Bay 0 runs at 54% peak area occupancy while the bound assumed
100%, and the blocks that would fix Z3 are refused not for want of space but because the
columns they need to descend through are fragmented.

Nothing in the pipeline can address that.  _balance moves ONE block to a bay that lowers the
objective, and p3max proved that neighbourhood empty on P3 -- evicting from bay 0 needs
gap/workload below 0.0948 and the cheapest resident is 0.145, so every single move loses.
_z3_improve reassigns without re-placing.  The beam places greedily in dispatch order and never
revisits.  Every one of them treats the existing arrangement as given, and the arrangement is
the problem.

WHAT IT DOES.  Take the bay under most pressure, lift EVERY block out of it, add the outsiders
that would most improve the objective by entering, and hand the whole set to cranepack -- the
weighted set-packing search over (orientation, x, y, entry) columns with the descent rule
enforced pairwise, validated against Gurobi earlier in this project.  Weights are objective
units, so it maximises value seated rather than block count: a resident carries what evicting
it would cost, an outsider what admitting it would gain.

WHY IT IS NOT A P3 SPECIAL CASE.  The target is chosen by measurement: bays are ranked by
u_j * load_j -- the quantity that sets Z2's maximum -- and the first one that some block would
profit by entering is taken.  Pressure alone is the wrong test, and the smoke test showed why:
an earlier version rotated strictly down the pressure order, and call two landed on a bay with
no profitable entrant, returned None in 0.0 s, and gave up the repeated application that is
where the gain compounds.  A bay nobody wants into cannot be repacked profitably however loaded
it is, because the objective only moves when a block changes bay.  On a saturated instance the
same operator buys Z1 instead of Z3 -- a bay that packs better admits blocks earlier and fewer
of them are late.  Nothing here tests density and nothing is tuned to one instance.

DISPLACEMENT IS THE POINT.  An earlier version of this rejected any repack that failed to
re-seat every resident.  That was measured wrong the moment the diagnostic ran: the repack that
took P3 from 96,990 to 82,175 re-seated 50 residents of 53 and displaced three, and the rule
would have thrown it away.  Trading a cheap resident out for an expensive entrant is not a
failure of the repack, it IS the repack, and the weights already price it.  So displaced blocks
are rehomed instead -- each is offered its bays in preference order and must find a legal seat
at its own unchanged times against the finished new state.  A block that cannot kills the
repack; it is NOT priced at its next-best bay and hoped for, which is exactly the assumption
that made every earlier P3 diagnostic report a wall that was not there.

SAFETY.  The rebuilt solution is verified with the real grader before it is returned, and
returning None always means the caller keeps what it had.
"""
import math
import os
import time

_CP = None
_CP_TRIED = False


# THE CONFLICT BUILD IS PARALLEL IN THE ENGINE AND HAS NEVER RUN THAT WAY (OGC_BRKTHREADS).
#
# cranepack's cost is its pairwise conflict graph: an O(ncol^2) loop calibrated at 6.4e-8 s per
# squared column, so ncol 11,580 costs 8.3 s and 24,318 costs 39.1 s.  OPSTAT prices the whole
# operator at 34.7 s on prob_1 and 36.1 s on prob_3, which is 22-23% of a worker.
#
# cranepack.so is built with OpenMP -- it carries GOMP_parallel -- and sizes that loop from
# omp_get_max_threads(), with per-thread edge buffers and memos merged afterwards and
# CRANEPACK_SERIAL=1 kept so the two paths can be shown to produce the same edge set.  It has
# been serial for the whole project because myalgorithm caps OMP_NUM_THREADS at module load and
# calls threadpool_limits(limits=1) inside every worker, both correctly: four workers times N
# threads oversubscribes four cores under a 400% throttle.
#
# Raising the cap globally would take the BEAM multi-threaded too, which is the thing the cap
# exists to prevent.  Raising it only around this call does not.  libgomp's omp_set_num_threads
# is reachable through ctypes -- verified in this container, 4 -> set(1) -> 1 -- so the threads
# go up immediately before pack() and back to one in a finally, and no other operator ever sees
# more than one.  No rebuild, so the shipped .so files stay in step with their sources.
#
# Default 1, which does not even dlopen: the guard below returns before loading, so the shipped
# path is what it was.
_GOMP = [None, False]


def _omp_threads(n):
    """Set OpenMP threads for this process.  Returns False if libgomp is not reachable."""
    if n <= 1 and not _GOMP[1]:
        return False                      # never loaded and not asked to raise: nothing to do
    if not _GOMP[1]:
        _GOMP[1] = True
        try:
            import ctypes
            _lib = ctypes.CDLL("libgomp.so.1")
            _lib.omp_set_num_threads.argtypes = [ctypes.c_int]
            _GOMP[0] = _lib
        except Exception:
            _GOMP[0] = None
    if _GOMP[0] is None:
        return False
    try:
        _GOMP[0].omp_set_num_threads(int(n))
        return True
    except Exception:
        return False


def _brk_threads():
    try:
        return max(1, min(8, int(os.environ.get("OGC_BRKTHREADS", "1"))))
    except Exception:
        return 1


def _load():
    global _CP, _CP_TRIED
    if not _CP_TRIED:
        _CP_TRIED = True
        try:
            import cranepack as _m
            _CP = _m
        except Exception:
            _CP = None
    return _CP


_LB_CACHE = {}
# call counter, which rotates the packer's SEED.  cranepack is deterministic and warm-started
# from the current layout, so without this a second call on the same bay re-derives its own
# previous answer, fails to beat it, returns None, and is then treated as starved -- its slice
# grows and the budget drains into a search that cannot move.  Process-local, which is what we
# want: each worker explores its own sequence.
_CALLS = [0]
# observed (time taken)/(time asked for) for the packer, blended across calls.  cranepack does
# not stop when its budget runs out, so this is the only honest input to how big a problem it
# is safe to hand over -- and it is measured on the machine actually running, not assumed.
_RATIO = [1.0]
# (grid step, outsiders, entry variants), largest first.  The packer's runtime is a property of
# the PROBLEM rather than of the deadline it is given: on P3 every large-tier call took 77-81 s
# whether it was asked for 35 s or 100 s.  So the operator takes the largest tier the remaining
# run can absorb, and predicts the cost rather than reading it off a table -- see below.
#
# nent=6 IS THE TOP TIER, and it lives here rather than in a constant because the same setting
# is a 7.2% gain on P3 and a disqualification on P4:
#
#     P3, three paired reps      nent 6: 80,795 / 80,795 / 84,990   mean 82,193
#                                nent 3: 88,695 / 86,085 / 90,970   mean 88,583
#     P4, forced, 480 s budget   nent 6: killed after 28 minutes
#
# P3's bay 0 is 43x23 and generates ~28,800 columns at this tier; P4's largest is 115x23 and
# generates 49,000-54,000, and the build is O(ncol^2).  The P4 run that ran away used FORCED
# knobs, which bypass the predictor -- unforced, the predictor already drops to a smaller tier
# on P4 by itself (traced).  So this belongs in the table where the cost model can refuse it,
# and never in a constant.
#
# WHY nent PAYS AT ALL.  It is how many entry times each block is offered when brk lifts a bay
# and repacks it.  A block's preferred bay is not full in the abstract, it is full AT THAT
# MOMENT, and more candidate times let the packer find the moment it fits.  P3 shows precisely
# that: Z3 502 -> 423, blocks reaching the bays they want, bought with Z2 2679 -> 3469 on an
# instance where a unit of preference is worth thirty of balance.
# nent is a FRACTION of the instance's own entry-time ceiling, not a count.  windows() draws
# its points into a SET, so any nent above a block's window width collapses to duplicates and
# the ladder's top rung was silently P3-shaped.  Measured on the real instances -- distinct
# entry times actually offered, averaged over blocks:
#
#     P3  width max  6     nent 3 -> 1.96   6 -> 2.12   9 -> 2.12   12 -> 2.12
#     P4  width max 11     nent 3 -> 2.57   6 -> 4.08   9 -> 4.46   12 -> 4.49
#     P6  width max 14     nent 3 -> 2.72   6 -> 4.58   9 -> 5.68   12 -> 6.10
#
# So 6 was not a fitted value on P3, it was P3's CEILING -- 9 and 12 are the same algorithm
# there.  But P6 has a third more resolution available and the constant threw it away.  The
# fractions below are a ladder SHAPE (full, half, third, sixth); the absolute numbers come from
# the instance.  On P3 they reproduce 6/3/2/1 exactly, which is the check that this changes
# nothing where the old table was right.
# OGC_TIERS overrides the NOUT column of the ladder, and it has to be done HERE rather than
# through BRK_NOUT.  Setting BRK_NOUT does not adjust the ladder: it takes the forced path, which
# bypasses the tier chooser AND sets _cap to -1, i.e. no time bound at all.  A sweep over it
# therefore measures an unbounded run, not a wider candidate list -- both arms timed out.
# (Fourth environment knob today that did something other than what its name suggests.)
_TIERS = [(4, 40, 1.0), (4, 40, 0.5), (4, 20, 1.0 / 3.0), (6, 10, 1.0 / 6.0)]
_TN = os.environ.get("OGC_TIERNOUT")
if _TN:
    try:
        _f = float(_TN)
        _TIERS = [(_s, max(1, int(round(_n * _f))), _e) for (_s, _n, _e) in _TIERS]
    except Exception:
        pass
# SECONDS PER SQUARED COLUMN.  The tier costs above were measured on P3 and do not transfer:
# the same table sent a P4 run 240 seconds past a 480-second budget, which at the grader's hard
# limit is a missing answer rather than a worse one.
#
# The reason is structural and it is in cranepack, not here.  Its conflict graph is built by a
# plain O(ncol^2) double loop with NO clock check in it -- the search loop honours
# time_budget_s, the build cannot even look at it.  So a pack that is too big cannot be cut
# short; it can only be declined before it starts.  A constant cannot do that, because the same
# tier generates a handful of columns in P3's 43x23 bay and a flood of them in a large one.
#
# What DOES transfer is the rate: seconds per squared column, on this machine, for this
# geometry.  The operator estimates the column count a tier would generate, predicts its cost
# from the running rate, and takes the largest tier the remaining run can absorb.  Unknown until
# the first call, so the first call takes the SMALLEST tier -- cheap everywhere, and it is what
# calibrates the rate.
#
# MEASURED, on P3 at two tiers, forcing the knobs and asking only 15 s so the build dominates:
#
#     tier (6,10,1)   ncol 11,580   build  8.3 s   ->  6.19e-8 s per squared column
#     tier (4,20,2)   ncol 24,318   build 39.1 s   ->  6.61e-8
#
# (24318/11580)^2 = 4.41 against a measured build ratio of 4.71, so the build really is
# O(ncol^2) and the rate is the same number at both sizes.  Predicting the large tier from it
# gives ~85 s, which is what the old hand-written table claimed (80 s): that table was RIGHT on
# P3 and simply could not travel, because it was seconds-per-TIER.  Seconds-per-squared-column
# travels, since the instance lives entirely in ncol.
#
# SEEDED rather than left unknown.  brk is called about ONCE PER WORKER in a run -- traced, four
# calls in a 240 s P3 run -- so a predictor that starts uncalibrated never gets a second call in
# which to spend what it learned.  That is why the previous version took the smallest tier every
# time while reporting 94-97 s of room.  Still corrected from cranepack's own build_ms on every
# call, so a different machine or bay shape moves it.
_PAIRRATE = [6.4e-8]
# has this process priced the machine it is running on?  See the calibration below.
_CALIB = [False, None]   # [done?, (ncol, rate, growth exponent)]
# The search is not predicted -- it runs for as long as it is ASKED, and we set the ask.  This is
# the least ask worth making: a tier whose build leaves less than this has nothing to search with
# and is a slow way of returning the warm start.
_MINASK = 8.0


_WISH_CACHE = {}
def _layers_bbox(B, bid):
    """Per-orientation (layer rasters, bbox) in cranepack's format.  Cached: a block's shape
    never changes and building the numpy layer list is the dominant cost of a call."""
    key = id(B), bid
    hit = _LB_CACHE.get(key)
    if hit is not None:
        return hit
    import numpy as np
    from utils import Block
    ol, ob = [], []
    for o in range(len(B[bid]["shape"])):
        blk = Block(block_id=bid, block_data=B[bid], x=0, y=0, orient_idx=o)
        Ls = blk.layers_at_pos()
        ol.append([np.ascontiguousarray(np.asarray(L, dtype=np.float64)) for L in Ls])
        xs = [p[0] for L in Ls for p in L]
        ys = [p[1] for L in Ls for p in L]
        ob.append((float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))))
    _LB_CACHE[key] = (ol, ob)
    return ol, ob


# HOW MANY BAYS GO INTO ONE REPACK.  One is the operator as it has always run.
#
# WHY MORE THAN ONE.  A one-bay repack can only admit an outsider by displacing a resident, and
# the displaced block must then find a seat in some other bay AT ITS OWN UNCHANGED TIMES against
# a state it cannot influence.  So a trade that needs both bays to move at once -- b leaves A for
# B while c leaves B for A, each fitting only in the hole the other opens -- is not merely hard
# for the one-bay neighbourhood, it is OUTSIDE it, and no amount of budget reaches it.  Two bays
# in one pack makes that trade a single decision of the set-packing search.
#
# WHY IT IS AFFORDABLE.  Columns in different bays can never conflict, so the conflict graph is
# the two per-bay graphs side by side: measured on a 53,252-column stress case, a second identical
# bay took n_cols 53,252 -> 106,504 and n_edges 95,965,518 -> 191,931,036, both exactly 2x.  The
# choice of bay costs nothing extra because the packer already admits at most one column per
# block, so which bay a block lands in is a selection the search was already making.
_NBAY = max(1, int(os.environ.get("OGC_BRKBAYS", "1")))


def repack(prob_info, sol, budget, total_fn, build_fn, engine_fn=None,
           nout=None, step=None, nent=None, hard=None, nbay=None):
    """One repack of the most contested bay (or of the most contested nbay bays together).
    Returns a better operations dict, or None.

    total_fn(prob_info, sol) -> (objective, checkdict)   the caller's own scorer, so this
    module never decides what "better" means.
    build_fn(list of assignment records) -> operations dict
    engine_fn(prob_info) -> ogc_fast Engine, used to rehome blocks the repack displaces.
    hard is the RUN's remaining seconds, not the slice.  The two differ by a lot -- the slice is
    the allocator's advisory share and the packer ignores deadlines anyway -- and the tier
    choice needs the run-level number, because a tier that costs 80 s is right with 190 s left
    and ruinous with 45.
    """
    CP = _load()
    if CP is None:
        return None
    try:
        B = prob_info["blocks"]; bays = prob_info["bays"]
        n = len(B); m = len(bays)
        if n == 0 or m < 2:
            return None
        w = prob_info["weights"]
        w1, w2, w3 = float(w["w1"]), float(w.get("w2", 0)), float(w["w3"])
        pref = [B[b]["bay_preferences"] for b in range(n)]
        mxp = [max(pref[b]) for b in range(n)]
        wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
        pt = [int(B[b]["processing_time"]) for b in range(n)]
        rel = [int(B[b]["release_time"]) for b in range(n)]
        due = [int(B[b]["due_date"]) for b in range(n)]
        bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
        u = [(sum(bar) / m) / bar[j] for j in range(m)]

        cur = [-1] * n; ent = [-1] * n; ext = [-1] * n; place = {}
        for t, ops in (sol or {}).get("operations", {}).items():
            for op in ops:
                b = op["block_id"]
                if op["type"] == "ENTRY":
                    cur[b] = op["bay_id"]; ent[b] = int(t)
                    place[b] = (int(op["orient_idx"]), float(op["x"]), float(op["y"]))
                else:
                    ext[b] = int(t)
        if any(cur[b] < 0 or ext[b] < 0 for b in range(n)):
            return None

        def obj_of(assign, entv, extv):
            load = [0.0] * m; z1 = 0.0; z3 = 0.0
            for b in range(n):
                load[assign[b]] += wl[b]
                z1 += max(0, extv[b] - due[b])
                z3 += mxp[b] - pref[b][assign[b]]
            v = [u[j] * load[j] for j in range(m)]
            return w1 * z1 + w2 * math.floor(max(v) - min(v)) + w3 * z3

        base = obj_of(cur, ent, ext)
        _CALLS[0] += 1
        k = _CALLS[0]

        # SIZE THE PROBLEM TO WHAT THE RUN CAN AFFORD, not to the slice.
        #
        # harness/brkcost.py measured this on the real hidden P3 and both columns are step
        # functions, which changes the whole design:
        #
        #     slice   took   ratio      obj     gain
        #        8s   20.3s   2.5x   105,430   -1.19%
        #       12s   18.9s   1.6x   105,430   -1.19%
        #       20s   21.0s   1.1x   105,430   -1.19%
        #       35s   77.0s   2.2x    91,670  -14.09%
        #       60s   78.5s   1.3x    91,670  -14.09%
        #      100s   81.0s   0.8x    91,670  -14.09%
        #
        # TIME IS SET BY THE PROBLEM, NOT THE BUDGET.  Every small-tier call costs about 20 s and
        # every large-tier call about 78 s, whatever they were asked for -- cranepack runs its
        # own search to completion and the deadline is advisory.  Handing it 100 s instead of 35
        # buys nothing; it finishes in 81 either way.
        #
        # AND SO IS THE GAIN.  -1.19% at the small tier, -14.09% at the large one, nothing in
        # between and nothing above.  The large tier is four times the cost for twelve times the
        # return, so it should be chosen almost always.
        #
        # WHICH EXPOSES THE BUG THIS REPLACES.  The old rule picked a tier from the slice, with
        # the large one gated at 40 s -- and brk's opening slot is worker_budget * 0.20, which at
        # a 240 s run is 39.8 s.  Just under.  Deflating by the observed ratio pushed it further
        # under.  So the operator was running in the -1.19% tier for the whole session while
        # -14.09% was one threshold away, and that is why giving it the entire budget changed
        # nothing: a bigger slice still bought the same small problem.
        #
        # The rule now asks the only question the measurement supports -- can the REMAINING RUN
        # time absorb this tier's measured cost -- and takes the largest tier that fits.  Costs
        # are learned per tier from what actually happens here, seeded with the numbers above,
        # so the rule adapts to a machine or an instance where they differ instead of trusting
        # a table.
        # THE INSTANCE'S ENTRY-TIME CEILING.  The widest tardiness-free window any block has;
        # nothing above it can produce a distinct entry time for any block, so it is the point
        # past which nent is free to ask for and worth nothing.
        _B = prob_info["blocks"]
        _CEIL = max(1, max((int(b["due_date"]) - int(b["processing_time"])
                            - int(b["release_time"]) + 1) for b in _B))

        def _ne_of(_frac):
            """A ladder rung as a count.  Fractions come from _TIERS, the ceiling from above."""
            return max(1, min(_CEIL, int(round(_frac * _CEIL))))

        _ev = (os.environ.get("BRK_STEP"), os.environ.get("BRK_NOUT"), os.environ.get("BRK_NENT"))
        SL = float(budget)
        _forced = not (step is None and nout is None and nent is None and not any(_ev))
        if _forced:
            STEP = int(step if step is not None else (_ev[0] or 4))
            NOUT = int(nout if nout is not None else (_ev[1] or 40))
            NENT = int(nent if nent is not None else (_ev[2] or 3))
        else:
            # DEFERRED.  A tier's cost is set by how many columns it generates, which depends on
            # the target bay's size and its resident count -- neither known yet.  Chosen below,
            # once TGT is fixed.  NOUT is needed before that only to bound the candidate list,
            # so the widest tier's value is used here and the list is truncated afterwards.
            STEP, NOUT, _f0 = _TIERS[0]
            NENT = _ne_of(_f0)

        # THE CONTESTED BAY: the most-pressed bay THAT ANYTHING WANTS TO ENTER.
        #
        # Pressure alone is the wrong test, and the smoke test showed why.  An earlier version
        # rotated the target strictly down the u_j*load_j order so repeated calls would not
        # re-derive one answer -- and the second call landed on a bay with no profitable
        # entrants, returned None in 0.0s, and gave up the one thing worth having.  Repeated
        # application from the operator's own output is where the gain compounds.
        #
        # So rank by pressure and take the first bay that has somewhere to go.  A bay nobody
        # wants into cannot be repacked profitably however loaded it is: the objective only
        # moves when a block changes bay, and the residents are already where they want to be.
        # The seed still rotates on every call, which is what stops a repeat visit from
        # re-deriving its own previous answer -- that was the real hazard, and it does not need
        # the target to move as well.
        _order = sorted(range(m), key=lambda j: -(u[j] * sum(wl[b]
                        for b in range(n) if cur[b] == j)))
        cands = []
        for j in _order:
            if not any(cur[b] == j for b in range(n)):
                continue
            got_outs = []
            for b in range(n):
                if cur[b] == j:
                    continue
                alt = list(cur); alt[b] = j
                g = base - obj_of(alt, ent, ext)
                if g > 0:
                    got_outs.append((g, b))
            if got_outs:
                got_outs.sort(reverse=True)
                cands.append((j, got_outs))   # truncated to NOUT after the tier is chosen
                break
        if cands:
            TGT, outs = cands[0]
        else:
            if os.environ.get("BRK_DEBUG") == "1":
                print("    brk: no bay has a profitable entrant anywhere", flush=True)
            return None

        # THE PARTNER BAYS.  With NB == 1 this loop does not run and everything below is the
        # one-bay operator unchanged.
        #
        # A partner is worth having in proportion to how much TRADE it has with TGT, in both
        # directions -- what TGT's residents would gain by moving there plus what its own
        # residents would gain by moving here.  Pressure is the wrong measure for the second bay
        # for the same reason it was the wrong measure for the first: a heavily loaded bay that
        # nobody wants to cross into contributes no decision the packer can make.  Summing the
        # POSITIVE single-move gains both ways is the cheapest quantity that answers the right
        # question, and it is exactly the trade the joint neighbourhood exists to find.
        NB = int(nbay) if nbay is not None else _NBAY
        NB = max(1, min(NB, m))
        BAYS = [TGT]
        if NB > 1:
            _sc = []
            for j in range(m):
                if j == TGT:
                    continue
                s = 0.0
                for b in range(n):
                    if cur[b] == TGT:
                        alt = list(cur); alt[b] = j
                        s += max(0.0, base - obj_of(alt, ent, ext))
                    elif cur[b] == j:
                        alt = list(cur); alt[b] = TGT
                        s += max(0.0, base - obj_of(alt, ent, ext))
                if any(cur[b] == j for b in range(n)):
                    _sc.append((s, j))
            _sc.sort(reverse=True)
            BAYS += [j for _s, j in _sc[:NB - 1]]
        BSET = set(BAYS)
        res = [b for b in range(n) if cur[b] in BSET]

        # A WINDOW OVER THE BAY SET, NOT BOTH BAYS WHOLE.
        #
        # Lifting every resident of every bay in the set is not a neighbourhood, it is the
        # instance.  The cost is worth stating exactly, because the 2x figure measured in
        # harness/cpequiv.py is easy to misread: THAT measurement held the candidate set fixed and
        # added a bay, and it is 2x.  The operator does not hold it fixed -- a second bay brings
        # its own residents -- so candidates double as well, and the pair work is 2 bays x (2x
        # candidates)^2 = 8x.  Traced on P20 with the old cost model: the smallest tier predicted
        # 65.7 s at one bay and 1,028 s at two, and the operator declined.
        #
        # So the joint pack takes as many candidates as the ONE-BAY pack would have, drawn from
        # both bays, and FREEZES the rest where they stand.  That is 2 bays x (same candidates)^2
        # = 2x, which is the affordable figure and the one that was measured.  Frozen blocks are
        # real obstacles -- cranepack drops any column that crane-conflicts with them -- so the
        # result is still a legal packing of the whole bay, not of a cleared one.
        #
        # WHICH residents.  A cross-bay trade is local in TIME: two blocks can only take each
        # other's space if they are in the yard together.  So the window is anchored on the block
        # with the most to gain by changing bay, and filled with the co-present residents of both
        # bays in gain order.  Nothing here is tuned -- the cap is the one-bay operator's own
        # resident count, and the anchor is chosen by the objective.
        frozen_res = []
        if NB > 1:
            # THE JOINT PACK MUST CONTAIN THE ONE-BAY PACK.
            #
            # The window used to be drawn from BOTH bays, and that quietly made the two-bay
            # neighbourhood a DIFFERENT one rather than a larger one: the target bay contributed
            # fewer of its own residents than the one-bay operator would have taken, the partner
            # was sampled on a coarser grid, and the residents left out stood in the way as frozen
            # obstacles.  A neighbourhood that is not a superset can be worse, and it was --
            # measured over eight instances, the one-bay arm improved seven and the two-bay arm
            # improved none, spending its full budget on each.
            #
            # So the target bay keeps ALL of its residents, exactly as the one-bay call would, and
            # the window applies only to the PARTNER.  Every selection the one-bay pack can make is
            # then available here, and anything the partner adds is extra.  The cost is the price
            # of that guarantee: candidates go from R to R + cap and both bays generate columns for
            # all of them, so the pair work is 2(R+cap)^2 against R^2.  OGC_BRKCAP sets cap as a
            # fraction of R -- at 0.4 that is about 4x the one-bay build, which the tier chooser
            # can decline on its own if the budget will not carry it.
            _tgt_res = [b for b in range(n) if cur[b] == TGT]
            _part_res = [b for b in res if cur[b] != TGT]
            _cap0 = max(1, int(round(len(_tgt_res)
                                     * float(os.environ.get("OGC_BRKCAP", "0.4")))))
            if _cap0 < len(_part_res):
                _g = []
                for b in _part_res:
                    _bg = 0.0
                    for j in BAYS:
                        if j == cur[b]:
                            continue
                        alt = list(cur); alt[b] = j
                        _bg = max(_bg, base - obj_of(alt, ent, ext))
                    _g.append((_bg, b))
                _g.sort(reverse=True)
                _anch = _g[0][1]
                _lo, _hi = ent[_anch], ext[_anch]
                _pick = [b for _v, b in _g if ent[b] < _hi and _lo < ext[b]][:_cap0]
                if len(_pick) < _cap0:
                    _have = set(_pick)
                    _pick += [b for _v, b in _g if b not in _have][:_cap0 - len(_pick)]
                _ps = set(_pick)
                frozen_res = [b for b in _part_res if b not in _ps]
                res = _tgt_res + _pick

        # OUTSIDERS, RE-RANKED OVER THE WHOLE BAY SET.  `outs` was built against TGT alone; with
        # a partner in play a block's value is the best it can do in ANY of the repacked bays,
        # and one that only wants the partner was not on the list at all.
        if NB > 1:
            _o = []
            for b in range(n):
                if cur[b] in BSET:
                    continue
                g = 0.0
                for jj in BAYS:
                    alt = list(cur); alt[b] = jj
                    g = max(g, base - obj_of(alt, ent, ext))
                if g > 0:
                    _o.append((g, b))
            _o.sort(reverse=True)
            outs = _o
            # NO OUTSIDERS IS NOT A DEAD END HERE, and on a two-bay instance it is the normal
            # case: BAYS is then the whole yard and every block is a resident by definition.  The
            # one-bay operator bails on an empty entrant list because nothing else can change in
            # a single bay -- with two, the residents can still trade places, which is the move
            # this exists for.  The test that the bay set is worth repacking at all was already
            # made when TGT was chosen.

        BDIM = [(float(bays[j]["width"]), float(bays[j]["height"])) for j in BAYS]
        W, H = BDIM[0]
        # GRID RESOLUTION PER BAY.  A single step across bays of different sizes is a resolution
        # chosen for the target and inherited by the partner, and on P3 that made the partner 8.4x
        # the cost of the target -- 159,430 columns against 18,884 -- for no reason other than
        # being bigger.  A bigger bay loses proportionally less by being sampled coarsely, because
        # it has more room to be wrong in, so the partner's step is raised until it costs no more
        # than the target.
        #
        # DERIVED FROM THE COLUMN COUNT, NOT FROM THE AREA.  sqrt(area) was the obvious scale and
        # it undershot: columns go as (W-w)(H-h), and in a big bay the block's own footprint
        # subtracts proportionally less, so an 8.4x column ratio came from an area ratio of about
        # 4 and the multiplier came out 2 where 3 was needed.  _ncol_est_bay already answers the
        # question exactly, so ask it instead of modelling it.  Per tier, because the step it is
        # scaling is the tier's.
        # THE RESIDENTS THAT STAY PUT, as obstacles in world coordinates.  cranepack drops any
        # generated column that crane-conflicts with one, so the window is repacked AROUND them
        # rather than into space they occupy.  The incumbent placement of every candidate survives
        # this by construction -- it coexists with these blocks in the solution being repacked --
        # so the warm start is never filtered away.
        #
        # Built HERE, before the tier is chosen, because the calibration below has to pack the
        # same shape: obstacles remove columns, and a rate calibrated without them is a rate for a
        # different problem.
        froz_in = []
        if frozen_res:
            import numpy as _np
            for _fb in frozen_res:
                _fol = _layers_bbox(B, _fb)[0][place[_fb][0]]
                _foff = _np.asarray([place[_fb][1], place[_fb][2]], dtype=float)
                froz_in.append(([_np.ascontiguousarray(_L + _foff) for _L in _fol],
                                int(ent[_fb]), int(ext[_fb]), BAYS.index(cur[_fb])))

        BMUL = [1] * len(BDIM)
        _BMC = {}

        def _bmul(_st, _no, _ne):
            _key = (_st, _no, _ne, len(res), len(outs))
            _hit = _BMC.get(_key)
            if _hit is not None:
                return _hit
            _n0 = _ncol_est_bay(_st, _no, _ne, BDIM[0][0], BDIM[0][1])
            _out = [1]
            for _W, _H in BDIM[1:]:
                _mm = 1
                while _mm < 16 and _ncol_est_bay(_st * _mm, _no, _ne, _W, _H) > _n0:
                    _mm += 1
                _out.append(_mm)
            _BMC[_key] = _out
            return _out

        def _ncol_est_bay(_st, _no, _ne, W, H):
            """Columns one bay of size (W,H) would generate at this tier."""
            return _ncol_est_of(res + [b for _, b in outs[:_no]], _st, _ne, W, H)

        def _ncol_est_of(_blocks, _st, _ne, W, H, _one_time=False):
            """The same count for an explicit block list.  _one_time is for the calibration, which
            offers each block a single entry variant rather than a window ladder."""
            _tot = 0
            for _b in _blocks:
                if _one_time:
                    _nt = 1
                    _, _ob = _layers_bbox(B, _b)
                    for _q in _ob:
                        _dw, _dh = _q[2] - _q[0], _q[3] - _q[1]
                        _nx = int((W - _dw) // _st) + 1
                        _ny = int((H - _dh) // _st) + 1
                        if _nx > 0 and _ny > 0:
                            _tot += _nx * _ny
                    continue
                _lo, _hi = rel[_b], due[_b] - pt[_b]
                if _hi < _lo:
                    _nt = 1
                else:
                    _ts = {_lo, _hi}
                    if _lo <= ent[_b] <= _hi:
                        _ts.add(ent[_b])
                    for _i in range(max(1, _ne)):
                        _ts.add(_lo + (_hi - _lo) * _i // max(1, _ne - 1) if _ne > 1 else _lo)
                    _nt = len(_ts)
                    _pr = prob_info["blocks"][_b].get("bay_preferences") or [0]
                    _w1e = float(prob_info["weights"]["w1"])
                    _w3e = float(prob_info["weights"].get("w3", 0.0))
                    if _w1e > 0.0 and _w3e * (max(_pr) - min(_pr)) >= _w1e:
                        _nt += max(1, int(os.environ.get("OGC_LATEK", "1")))
                _, _ob = _layers_bbox(B, _b)
                for _q in _ob:
                    _dw, _dh = _q[2] - _q[0], _q[3] - _q[1]
                    _nx = int((W - _dw) // _st) + 1
                    _ny = int((H - _dh) // _st) + 1
                    if _nx > 0 and _ny > 0:
                        _tot += _nx * _ny * _nt
            return float(_tot)

        # NOW the tier can be chosen, because the column count is computable.  cranepack builds
        # its conflict graph with an O(ncol^2) double loop that never looks at the clock, so an
        # oversized pack cannot be cut short -- only declined before it starts.  Predict from the
        # measured seconds-per-squared-column, take the largest tier the run can absorb, and if
        # even the smallest does not fit, do not call the packer at all.
        _tier = -1
        if not _forced:
            # Half the room, not all of it: what is predicted is the BUILD, and the solve
            # that follows runs for as long as it is asked.  A tier whose build alone fills the
            # budget leaves nothing to search with, which is a slow way of returning the warm
            # start.
            # The same cap the pack is given, for the same reason: a tier whose build alone
            # fills the cap leaves nothing to search with.  That cap is the RUN's remaining
            # time, not the operator's slice -- see the note at the ask.
            _room = (float(hard) if hard is not None else SL) * 0.85

            def _ncol_est(_st, _no, _ne):
                """Columns a tier would generate, per block, per orientation, per entry time.

                Two corrections, each found by comparing against the count cranepack returns.

                TIMES: windows() below offers the tardiness-free bounds, the block's own entry
                time, and _ne sampled points -- up to _ne + 2 DISTINCT values, not _ne.  Using
                _ne under-counted by 1.3x to 2.8x, unevenly across tiers, which biases the tiers
                against each other rather than scaling them alike.

                POSITIONS: a block cannot start where it would hang off the bay, so the grid it
                can use is (W - w) / step, not W / step.  Ignoring its footprint over-counted by
                2.5x on P3 -- estimate 28,672 against a real 11,282 -- and squaring that made the
                predicted build 52.6 s where it measured 7.7 s, which is why every tier still
                looked unaffordable.

                BAYS: with more than one bay the same block is offered positions in each, so the
                count is summed over BDIM.  What is RETURNED, though, is not that sum -- the cost
                model squares its argument, and the pair loop's work is the sum of the per-bay
                triangles, not the triangle of the total, because cross-bay pairs are never
                enumerated.  Returning sqrt(sum of squares) is the column count whose SQUARE is
                the real work, which is what _pred is about to multiply.  Getting this wrong is
                not conservative in a harmless direction: it would predict 4x for a 2x build and
                make the chooser step down a tier it could afford."""
                _mu = _bmul(_st, _no, _ne)
                BMUL[:] = _mu
                _per = [_ncol_est_bay(_st * _mu[_i], _no, _ne, _W, _H)
                        for _i, (_W, _H) in enumerate(BDIM)]
                if len(_per) > 1 and os.environ.get("BRK_DEBUG") == "1":
                    print("      ncol_est per bay %s  step x%s  (cand=%d res=%d frozen=%d)"
                          % (["%.0f" % _v for _v in _per], BMUL,
                             len(res) + min(len(outs), _no), len(res), len(frozen_res)),
                          flush=True)
                return math.sqrt(sum(_v * _v for _v in _per))


            # CALIBRATE THE RATE ON THIS MACHINE, ONCE, BEFORE CHOOSING.
            #
            # _PAIRRATE was a constant measured on one host and never updated before a tier was
            # picked -- it only adapts AFTER a call, and brk fires about once per worker, so the
            # correction never arrives in time.  When the container moved to a slower host the
            # same P3 build went 61.8 s -> 91.8 s at the same column count on an idle machine,
            # the predictor still said 60.6 s, the chooser took a tier that did not fit an 83 s
            # cap, the build correctly refused it, and brk did nothing at all on all four
            # workers: P3 80,795 -> 100,685, which is brk-off.
            #
            # So measure it here.  One pack on a deliberately coarse grid costs about a second
            # and prices the machine actually running.  time_budget_s is ~0 because only the
            # BUILD is being timed; the search is not wanted and does not run.
            if _PAIRRATE[0] is not None and not _CALIB[0]:
                _CALIB[0] = True
                try:
                    # TWO POINTS, AND A FIXED COST.  The two points were here to give a growth
                    # EXPONENT -- small column sets fit in cache and large ones do not, so the
                    # rate was expected to rise with n and a single micro-build to be optimistic.
                    # Measured on the real instances, the fit came out the other way every time:
                    #
                    #     P20   848 cols -> 5.28e-08     2,328 -> 1.05e-08
                    #     P13   502      -> 1.61e-07     1,420 -> 2.36e-08
                    #
                    # The rate FALLS 5-7x over an octave, the exponent clamps at zero, and the
                    # larger point is taken.  That is not cache behaviour reversing, it is the fit
                    # being wrong: build_ms covers PARSING and column generation as well as the
                    # pair loop, and at 848 columns those are nearly all of it.  848 cols took
                    # 38.0 ms and 2,328 took 56.9 ms -- 7.5x the pairs for 1.5x the time, which
                    # is a constant with a small slope on top, and dividing a constant by n^2
                    # manufactures a rate that falls like 1/n^2.
                    #
                    # The consequence was not a small error.  On P20 the fitted rate predicted
                    # 65.7 s for a build that took 15.0 s, so the chooser dropped to the smallest
                    # tier; on P13 it predicted 129 s against 102 s of room and DECLINED TO RUN AT
                    # ALL, at a 120 s budget.  brk has been switched off on these instances by its
                    # own cost model, which is what "repack returned nothing" was really reporting.
                    #
                    # Two points and two unknowns: build(n) = c + r*n^2, solved rather than
                    # assumed.  On the P20 numbers that is 0.035 s + 4.03e-09/col^2, predicting
                    # 25.2 s where the old model said 65.7 s and the truth was 15.0 s -- still
                    # conservative, which is the safe direction, but no longer by 4.4x.
                    _cb, _cbb = [], []
                    for _b in (list(res) + [b for _g, b in outs])[:24]:
                        _ol, _ob2 = _layers_bbox(B, _b)
                        _cb.append((_ol, _ob2, [(ent[_b], ext[_b])]))
                        _cbb.append((_b,))
                    # REFINE UNTIL THE PAIR LOOP IS THE MEASUREMENT.  Two fixed steps, 24 and 12,
                    # produced builds 30 ms apart of which the fixed cost was 77% -- and the fit
                    # takes their DIFFERENCE, so a 10% timing wobble became a 5x error in the
                    # slope.  It did: on P20 the same machine fitted 3.73e-09 in one arm and
                    # 1.89e-08 in the next, against a real 2.45e-09, and the 8x-high one declined
                    # a tier it could afford four times over.
                    #
                    # Halve the step until the build is big enough that the pair loop dominates,
                    # and stop as soon as it is -- which bounds the calibration by its own last
                    # measurement rather than by a guess about how big a bay might be.  The span
                    # between the first and last point is then wide enough that the difference is
                    # signal.
                    # AND IN THE ESTIMATOR'S OWN UNITS, against the same obstacles.
                    #
                    # The rate was fitted against cranepack's REAL column count and then used to
                    # predict from _ncol_est, which is an upper bound -- it counts positions the
                    # packer discards, and now also the columns the frozen residents kill.  The
                    # units did not match, and _pred squares its argument, so the mismatch is
                    # squared too.  Measured across eight instances:
                    #
                    #     one bay, no obstacles     est/real 1.08 to 1.44     -> 1.2x to 2.1x high
                    #     two bays, with obstacles  est/real 3.30 and 4.95    -> 11x to 25x high
                    #
                    # 25x is why the two-bay arm declined on five of eight instances while the
                    # build it was refusing measured 0.7 s.  Fitting against OUR OWN estimate makes
                    # the bias part of the constant instead of part of the answer, and packing the
                    # calibration against the same obstacles keeps the shape the same as well --
                    # a rate calibrated on an unobstructed bay is a rate for a different problem.
                    _cfroz = [_f for _f in froz_in if _f[3] == 0]
                    _pts = []
                    if _cb:
                        _cst = 24
                        while _cst >= 3:
                            _cr = CP.pack(_cb, W, H, _cst, 0.01, seed=1, warm=None,
                                          frozen=_cfroz, weights=[1.0] * len(_cb))
                            _cn = _ncol_est_of([_q[0] for _q in _cbb], _cst, 1, W, H,
                                               _one_time=True)
                            _cbuild = float(_cr[4]) / 1000.0
                            if _cn > 200.0 and _cbuild > 0.005:
                                _pts.append((_cn, _cbuild))
                            if _cbuild > 0.25 or len(_pts) >= 5:
                                break
                            _cst //= 2
                    if len(_pts) >= 2 and _pts[-1][0] > _pts[0][0] * 1.5:
                        (_n1, _b1), (_n2, _b2) = _pts[0], _pts[-1]
                        _r = (_b2 - _b1) / (_n2 * _n2 - _n1 * _n1)
                        _c = _b1 - _r * _n1 * _n1
                        if _r <= 0.0:
                            # the slope did not survive the noise; charge it all to the rate,
                            # which is the old behaviour and errs high
                            _r, _c = _b2 / (_n2 * _n2), 0.0
                        _CALIB[1] = (max(0.0, _c), _r)
                        _PAIRRATE[0] = _r
                    elif _pts:
                        _CALIB[1] = (0.0, _pts[-1][1] / (_pts[-1][0] ** 2))
                        _PAIRRATE[0] = _CALIB[1][1]
                    if os.environ.get("BRK_DEBUG") == "1" and _CALIB[1]:
                        print("    brk calib: %s -> fixed %.3fs + %.3g s/col^2"
                              % (" ".join("%d:%.1fms" % (int(n), 1000.0 * b) for n, b in _pts),
                                 _CALIB[1][0], _CALIB[1][1]), flush=True)
                except Exception as _e:
                    # never silent: a calibration that cannot run leaves the seeded rate in
                    # place, and the seed is exactly what was wrong the last time this mattered
                    if os.environ.get("BRK_DEBUG") == "1":
                        print("    brk calib FAILED (%s) -- keeping the seeded rate" % _e,
                              flush=True)

            def _pred(_nc):
                """Seconds the build will take at _nc columns, on THIS machine."""
                if _CALIB[1] is None:
                    return _PAIRRATE[0] * _nc * _nc
                _c0, _r0 = _CALIB[1]
                return _c0 + _r0 * _nc * _nc

            _pick = None
            for _ti, (_st, _no, _fr) in enumerate(_TIERS):
                _ne = _ne_of(_fr)
                _nc = _ncol_est(_st, _no, _ne)
                # build + the least ask worth making has to fit; the ask itself is set below
                # from whatever the build leaves, so the two together never exceed the room.
                if _pred(_nc) + _MINASK <= _room:
                    _pick = (_ti, _st, _no, _ne, _nc)
                    break
            if _pick is None:
                _ti = len(_TIERS) - 1
                _st, _no, _fr = _TIERS[_ti]
                _ne = _ne_of(_fr)
                _nc = _ncol_est(_st, _no, _ne)
                if _pred(_nc) + _MINASK > _room:
                    if os.environ.get("BRK_DEBUG") == "1":
                        print("    brk: declined, smallest tier predicts %.0fs of %.0fs"
                              % (_pred(_nc), _room), flush=True)
                    return None
                _pick = (_ti, _st, _no, _ne, _nc)
            _tier, STEP, NOUT, NENT, _NCOL = _pick
            if os.environ.get("BRK_DEBUG") == "1":
                print("    brk tier: room=%.0fs rate=%s -> tier %d (step %d nout %d nent %d)"
                      " ncol~%.0f pred=%.1fs  [hard=%s slice=%.0fs]"
                      % (_room, ("%.3g" % _PAIRRATE[0]) if _PAIRRATE[0] is not None else "-",
                         _tier, STEP, NOUT, NENT, _NCOL,
                         _pred(_NCOL) if _PAIRRATE[0] is not None else -1.0,
                         ("%.0f" % hard) if hard is not None else "-", SL), flush=True)
        else:
            _NCOL = 0.0
        outs = outs[:NOUT]

        # HOW LATE IS IT WORTH BEING, priced from the instance's own weights.
        #
        # windows() offered only tardiness-free entry times, and on the preliminary set that was
        # right: w1 ran 6,667..21,622 against w3 133..200, so one day of lateness cost at least
        # 33 preference points and the trade essentially never paid.  The final-round practice
        # instances invert that -- w1 falls to 333 and w3 rises to 800, where a day of lateness
        # costs 0.4 preference points.  A block that could reach its preferred bay by waiting one
        # day is then obviously worth delaying, and the operator could not even consider it.
        #
        # The bound is derived, not chosen: delaying block b by d costs w1*d and can gain at most
        # w3 * (its current preference regret), so no delay beyond w3*regret/w1 can ever pay.
        #
        # PRICING, and it is why this cannot simply offer more windows.  cranepack's weight is
        # per BLOCK (wt[block]), not per column, so it cannot tell a tardy window from an on-time
        # one -- offering both without adjustment would let it take the late seat for free.  So a
        # block is offered at most ONE late window and its weight is reduced by that window's
        # tardiness cost below.  If the late seat is taken the price is exact; if the on-time seat
        # is taken the block is undervalued, which is conservative rather than wrong.
        _w1f = float(prob_info["weights"]["w1"]); _w3f = float(prob_info["weights"].get("w3", 0.0))
        _LATE = os.environ.get("OGC_LATEWIN", "1") != "0"
        # OGC_WINW=0 sends the old per-block weights, so the two pricings can be paired against
        # each other on the same engine.  Default on: it is the correct price, and cranepack is
        # byte-identical when the argument is absent.
        _WINW = os.environ.get("OGC_WINW", "1") != "0"

        def _late_by(b):
            if not _LATE or _w1f <= 0.0:
                return 0
            _reg = max(pref[b]) - pref[b][cur[b]]
            if _reg <= 0:
                return 0
            return max(0, min(int(_CEIL), int(_w3f * _reg / _w1f)))

        # HOW MANY LATE WINDOWS, AND WHERE.  The single late window used to be placed at
        # _late_by(b) = w3*regret/w1, the BREAK-EVEN delay -- and break-even is by definition
        # where the seat is worth nothing.  Under per-block weights that was forced: one window
        # was all that could be priced, so it went to the widest opening.  Under per-seat prices
        # it is simply the worst point on the curve, since price(d) = gain - w1*d falls with d.
        #
        # It shows up in the split between the instances per-seat pricing wins and loses:
        #
        #     wins  (22)   median dZ3  -6    median w3/w1 0.085   w1*Z1 share 77.9%
        #     loses (10)   median dZ3 +157   median w3/w1 0.022   w1*Z1 share 87.5%
        #
        # The losers are tardiness-dominated instances where preference is four times cheaper,
        # so a seat at break-even is not merely worthless there, it is reliably worthless -- and
        # it still costs columns and dilutes the choice.
        #
        # The reason a LARGE delay was ever wanted is that the preferred bay may not free up
        # sooner.  That is an argument for offering several and letting the price decide, which
        # per-seat weights now make possible: a ladder from one day to break-even, geometric so
        # the cheap end is sampled densely.  No gate and no tuned constant -- the endpoints come
        # from the instance's own weights and the count is bounded to keep the column count sane.
        _LATEK = max(1, int(os.environ.get("OGC_LATEK", "1")))

        def windows(b):
            """Entry times to offer: the tardiness-free window, plus a geometric ladder of late
            entries between one day and the break-even delay this instance's weights imply."""
            lo, hi = rel[b], due[b] - pt[b]
            if hi < lo:
                return [(ent[b], ent[b] + pt[b])]
            ts = {lo, hi}
            # THE BLOCK'S OWN SEAT IS ALWAYS OFFERED.  This used to be conditional on the current
            # entry lying inside the tardiness-free window, which quietly excluded every block
            # that is ALREADY LATE -- and those are exactly the blocks a repack is called on to
            # deal with.  A resident whose current time is not offered cannot be seated where it
            # already sits, so the packer has no way to reproduce the incumbent for it and drops
            # it; the operator then has to rehome it, and if it cannot, the whole repack dies.
            #
            # Measured on P3: 12 of 52 residents displaced at one bay and 14 at two, which is not
            # a legalisation edge case, it is a quarter of the bay being evicted for no reason.
            # An operator must always be able to return what it was given.  ent[b] >= rel[b] holds
            # because the solution being repacked is feasible.
            ts.add(ent[b])
            for i in range(max(1, NENT)):
                ts.add(lo + (hi - lo) * i // max(1, NENT - 1) if NENT > 1 else lo)
            _d = _late_by(b)
            if _d > 0:
                if _LATEK <= 1:
                    ts.add(hi + _d)
                else:
                    for _k in range(_LATEK):
                        # d, d/2, d/4, ...  taken from the far end so break-even stays offered
                        _dd = max(1, int(_d / (2 ** _k)))
                        ts.add(hi + _dd)
            return [(t, t + pt[b]) for t in sorted(ts)]

        cand = list(res) + [b for _, b in outs]
        isres = [True] * len(res) + [False] * len(outs)
        blocks_in = []
        for b in cand:
            ol, ob = _layers_bbox(B, b)
            blocks_in.append((ol, ob, windows(b)))

        # WEIGHTS.  cranepack maximises the total weight it can seat, so a weight has to mean
        # "what seating this block is worth" in objective units.
        #
        # WHY THE OBVIOUS WEIGHT IS WRONG FOR A SET.  The weights below the switch are
        # SINGLE-MOVE deltas: move this one block, keep everything else, read the objective.
        # That is exact for one block and wrong for the twenty the packer decides at once,
        # because Z2 is a RANGE -- w2 * (max_j u_j*load_j - min_j u_j*load_j).  A range is
        # neither linear nor separable, so a sum of single-move deltas is not the delta of the
        # sum.  Two blocks that each look worth having can be worthless together (the first one
        # takes the extreme bay off its peak and the second buys nothing), and two that each
        # look worthless can pay together.  The packer has no way to know either.
        #
        # THE FIX, AND WHY IT IS NOT AN APPROXIMATION IN DISGUISE.  The range is PIECEWISE
        # LINEAR: hold which bay is the argmax and which is the argmin, and inside that regime
        # the objective is exactly linear in the loads, with a closed-form coefficient per
        # block.  So price each candidate by the difference between its two possible fates --
        # seated in TGT, or its fallback (stay where it is, for an outsider; the next-best bay,
        # for a resident) -- under the current regime.  That is the true derivative rather than
        # a first difference, and derivatives DO sum.  If the repack moves enough load that the
        # extreme bays change hands the pricing degrades, and that costs search quality only:
        # the rebuilt solution is still scored by the real grader at the end and a repack that
        # does not actually pay is still thrown away.
        _hi = max(range(m), key=lambda j: u[j] * sum(wl[q] for q in range(n) if cur[q] == j))
        _lo = min(range(m), key=lambda j: u[j] * sum(wl[q] for q in range(n) if cur[q] == j))

        def _z2c(b, j):
            """d(w2*Z2)/d(putting b in bay j), under the current argmax/argmin regime."""
            if j == _hi:
                return w2 * u[j] * wl[b]
            if j == _lo:
                return -w2 * u[j] * wl[b]
            return 0.0

        def _z3c(b, j):
            return w3 * (mxp[b] - pref[b][j])

        # PRICE THE SEAT, NOT THE BLOCK.
        #
        # This used to discount the block's weight by the late window's tardiness, because
        # cranepack indexed weights by BLOCK and could not tell one of its seats from another.
        # That discount is wrong in both directions: the block is undervalued whenever it takes
        # the on-time seat, and since the late window is offered at the break-even delay
        # w3*regret/w1, the discount equals the whole gain -- the highest-regret blocks kept
        # 0.0% of their value on prob_40 and 8.3% on prob_36 and hit the 1.0 floor, which is
        # precisely the blocks the repack exists to move.
        #
        # cranepack now takes win_weights[i][k], the value of seating candidate i at its k-th
        # offered window, so each seat carries its own price and nothing has to be discounted.
        # The delta is exact: relative to where the block sits today, moving its entry to a
        # window ending at `ex` changes tardiness by max(0, ex - due) - max(0, ext - due), and
        # that is the only term in the objective an entry time can touch.  A window EARLIER than
        # today's is priced above the base for the same reason, which the block-weighted version
        # could not express either.
        # WITH SEVERAL BAYS THE SEAT IS (BAY, WINDOW), not the window alone -- bay is what Z3
        # reads, so the same block at the same time is worth different amounts in each.  The row
        # is laid out bay-major, cranepack indexes it bay*len(windows) + variant, and at one bay
        # that index is the variant and the layout is the one that was there before.
        #
        # The value of a seat is what it is worth ABOVE THE BLOCK'S FALLBACK -- where the block
        # ends up if the packer does not take it.  For an outsider that is where it sits today;
        # for a resident of one of the repacked bays it is the best bay OUTSIDE the set, because
        # that is where the rehoming step will actually put it.  With one bay both reduce to the
        # expressions this replaces, exactly.
        _out_of = [j for j in range(m) if j not in BSET]

        def _fallback(b, is_res):
            if not is_res:
                return cur[b]
            if not _out_of:
                return cur[b]
            return max(_out_of, key=lambda j: pref[b][j])

        # WHICH RESIDENTS HAVE NOWHERE TO GO.
        #
        # The packer prices a resident at what evicting it would cost -- the objective of putting
        # it in its next-best bay -- and is free to drop the cheap ones to admit a valuable
        # entrant.  That pricing assumes the next-best bay will TAKE it, and the measurement says
        # that assumption is what breaks: on P3 the operator displaced eight residents, could not
        # rehome one of them, and the whole repack was thrown away.  Retrying in a different order
        # settled the question -- placed FIRST, into a yard holding only the blocks that had not
        # moved, b101 still fitted in no bay on any of sixteen days.  It is not the order.  There
        # is no seat, and no pricing of a seat that does not exist can be right.
        #
        # So ask, before the pack: can this resident leave at all?  Against a yard emptied of every
        # block in the repacked bays, which is MORE room than it will really have, so a block that
        # fails here fails for certain.  Those get a weight no combination of entrants can outbid;
        # they can still move within the repacked bays, which is where the packing gain comes from,
        # but they cannot be evicted from them.  Nothing is frozen and nothing is gated -- the
        # weight is derived from the entrants' own gains, so on an instance where everyone has
        # somewhere to go this changes nothing at all.
        _STICK = set()
        if engine_fn is not None and os.environ.get("OGC_BRKSTICK", "1") != "0":
            _oth = [j for j in range(m) if j not in BSET]
            if _oth:
                try:
                    _E0 = engine_fn(prob_info)
                    _E0.clear_all()
                    for q in range(n):
                        if cur[q] not in BSET:
                            _E0.add(int(cur[q]), int(q), int(place[q][0]), float(place[q][1]),
                                    float(place[q][2]), int(ent[q]), int(ext[q]))
                    _pk = max(1, int(os.environ.get("OGC_BRKPRECHK", "4")))
                    for _b in res:
                        _ok = False
                        for _d in range(_pk):
                            for _j in _oth:
                                if len(_E0.feasible_scan(int(_b), [int(_j)], int(ent[_b] + _d),
                                                         int(ext[_b] + _d), 1)):
                                    _ok = True
                                    break
                            if _ok:
                                break
                        if not _ok:
                            _STICK.add(_b)
                except Exception:
                    _STICK = set()
        # bigger than every entrant put together, so no set of admissions pays for one eviction
        _STICKY = 1.0 + sum(float(_g) for _g, _ in outs) + float(len(res))
        if os.environ.get("BRK_DEBUG") == "1":
            print("    brk stick: %d of %d residents cannot leave the bay set at all"
                  % (len(_STICK), len(res)), flush=True)

        def _price(cand_l, isres_l, blocks_l):
            """(block weights, per-seat weights) for a candidate list and its offered windows.

            A function rather than a block because the tier step-down rebuilds the windows and
            therefore has to re-price.  It used to re-derive the rows from the OLD wts, which is
            stale by one rung; here it is simply called again."""
            _wts, _winw = [], []
            for _i, _b in enumerate(cand_l):
                _af = list(cur); _af[_b] = _fallback(_b, isres_l[_i])
                _of = obj_of(_af, ent, ext)
                _t0 = max(0, ext[_b] - due[_b])
                _row = []
                for _j in BAYS:
                    _aj = list(cur); _aj[_b] = _j
                    _w = _of - obj_of(_aj, ent, ext)
                    if isres_l[_i]:
                        _w = _STICKY if _b in _STICK else max(1.0, _w)
                    _row += [max(1.0, _w - _w1f * (max(0, _ex - due[_b]) - _t0))
                             for (_en, _ex) in blocks_l[_i][2]]
                _winw.append(_row)
                _wts.append(max(1.0, max(_row)))   # the block's rank is its best seat
            return _wts, _winw

        wts, winw = _price(cand, isres, blocks_in)

        # the entry goes with the position: without it the packer seeds the right layout at the
        # wrong schedule and cannot reproduce what it was given
        warm = [(i, place[b][0], int(place[b][1]), int(place[b][2]), BAYS.index(cur[b]),
                 int(ent[b])) for i, b in enumerate(cand) if isres[i]]

        t0 = time.time()
        # ASK FOR LESS THAN WE HAVE.  cranepack overruns whatever it is told, so the deadline
        # handed to it is deflated by the observed ratio rather than being the time remaining.
        # q14_wide_r1 finished a 240 s run in 260 s: the ratio adapts from the PREVIOUS call, so
        # a call that starts near the end of the budget overruns before the estimate can react,
        # and at the grader's hard limit that is a truncated answer rather than a slow one.
        # Deflating the ask makes the FIRST call inside a run safe too, not just the ones after
        # the estimate has settled.
        _left = float(budget) - (time.time() - t0)
        _ask = max(1.0, _left / max(1.0, _RATIO[0]))
        _cap = -1.0            # no cap on the forced path, which bypasses the chooser entirely
        if _tier >= 0 and _NCOL > 0.0:
            # A call costs BUILD + ASK and only the ask is ours to set, so SUBTRACT rather than
            # take a minimum.  The previous form was
            #
            #     _ask = max(_MINASK, min(_left / _RATIO, room - predicted_build))
            #
            # whose first term comes from the SLICE and is unrelated to room, so it passed
            # straight through whenever it was the smaller of the two.  Traced on P6:
            #
            #     build 112.2 s + ask 171.8 s = 286.3 s     against a 172 s slice
            #     build 213.3 s + ask 171.8 s = 386.0 s
            #
            # One call spending 2.2x its share, and the run finishing in 1014 s against a 900 s
            # budget.  Subtracting from a cap that includes the build makes build + search <= cap
            # structural instead of coincidental.
            #
            # THE CAP IS THE RUN DEADLINE, NOT THE SLICE.  Capping on the slice also caps the
            # TIER CHOOSER, and on P3 that switched off the one lever measured to matter:
            #
            #     room 97s -> tier 0 (4,40,6)  ncol~31,142    87,990 / 86,635  (forced: 80,795)
            #     room 40s -> tier 3 (6,10,1)  ncol~11,402    94,630 / 91,250
            #
            # 2.7x fewer columns for 5,600 of objective.  P3 gives hard=114 s and a 40 s slice,
            # and one number was answering two questions: how long may THIS call run, and what
            # share of the run does this OPERATOR deserve.  Only the first is a deadline.
            #
            # What made the slice look necessary was the build PREDICTION, not the cap.  On P6
            # the rate said 119 s and the build took 213 s, so build + ask overshot whatever it
            # was subtracted from.  cranepack now takes total_s and subtracts its own MEASURED
            # build, so the deadline holds without predicting anything, and _ask below is only a
            # hint.  A mispredicted tier costs search time -- quality -- and never the deadline.
            #
            # AND THE ASK IS THE CAP, not the cap minus a predicted build.  Subtracting here
            # charged for the build TWICE -- once in the prediction, once again when cranepack
            # truncated the search against its own measured build -- and every second the
            # prediction ran pessimistic was search time thrown away.  Measured on P3, two reps
            # each, interleaved:
            #
            #     ask = cap                       80,795   80,795
            #     ask = cap - predicted build     87,990   87,990
            #     tier 0 forced (old ask path)    80,795   80,795
            #
            # 7,195 of objective, reproducible to six figures.  This cannot endanger the
            # deadline: what truncates the search is total_s minus the REAL build, and _ask is
            # only an upper hint on top of it.
            # TWO BOUNDS, each answering its own question.  _cap keeps the CALL inside the
            # run's deadline; _ask keeps this OPERATOR inside its share so the others still get
            # theirs.  cranepack takes the tighter of the two against its own measured build, so
            # neither has to predict anything -- which is what broke this twice today, once by
            # charging the build to the search and once by charging column generation to the
            # pair loop.
            #
            # _ask is the SLICE, unmodified.  Subtracting a predicted build from it was the
            # double charge worth 7,195 on P3, and letting it run to _cap was what put P4 at
            # 491 s of a 480 s budget once the build stopped being the expensive part.
            _cap = (float(hard) if hard is not None else SL) * 0.85
            _ask = max(_MINASK, SL)
            # AND THE CALL IS BOUNDED BY THE SLICE, not just its search.  _ask only truncates the
            # SEARCH; the build is uninterruptible and was charged against _cap, i.e. 85% of the
            # whole remaining run.  So a call actually cost build + slice, and on the final-round
            # practice prob_1 that was 26.5 s + 29 s = 55.9 s against a 28.8 s slice -- twice its
            # allowance, twice in a row, both failing with "could not be rehomed", consuming 63%
            # of the budget before the bandit could measure brk's rate at all.  Removing brk was
            # worth 8.9% there, and the submitted run lost that instance's hidden counterpart by
            # 10.8%.
            #
            # total_s bounds build + search against cranepack's OWN MEASURED build, so passing
            # the slice here is not the predicted-build double charge that cost 7,195 on P3 --
            # nothing is predicted.  A tier whose build alone will not fit the slice is refused
            # and the operator steps down a tier, which is the behaviour already built for it.
        # AN ABORTED BUILD STEPS DOWN A TIER INSTEAD OF GIVING UP.
        #
        # The predictor can be wrong -- it was, on P3, the moment the container moved to a host
        # where the same 30,000-column build went 61.8 s -> 91.8 s.  The chooser took a tier that
        # no longer fitted an 83 s cap, the build correctly refused it, and brk returned None on
        # all four workers: 80,795 -> 100,685, which is brk switched off.
        #
        # A better predictor would not fix that, only postpone it: any prediction is wrong on
        # some machine.  What fixes it is what happens NEXT.  An abort is cheap -- 1.6 s, because
        # the projection fires within the first few hundred rows -- so the honest response is to
        # take the next tier down and try again.  The operator then degrades one rung at a time
        # instead of vanishing, and the total spent on refused builds is bounded by the ladder.
        _rest = list(range(_tier + 1, len(_TIERS))) if _tier >= 0 else []
        # Threads up for the packer only.  The finally is the load-bearing half: a count left
        # raised on an exception path would hand the BEAM extra threads for the rest of the
        # worker, which is exactly the oversubscription the module-level cap prevents.
        _nth = _brk_threads()
        _raised = _omp_threads(_nth) if _nth > 1 else False
        try:
          while True:
            _pt = time.time()
            r = CP.pack(blocks_in, W, H, STEP, _ask,
                        seed=12345 + 7919 * k, warm=warm or None, frozen=froz_in,
                        weights=[float(x) for x in wts],
                        total_s=min(_cap, SL),
                        **({"win_weights": winw} if _WINW else {}),
                        # only when there is more than one, so the single-bay call is the call
                        # that has always been made -- proved identical by harness/cpequiv.py
                        **({"bays": [(_W, _H, STEP * BMUL[_i])
                                     for _i, (_W, _H) in enumerate(BDIM)]}
                           if len(BDIM) > 1 else {}))
            if not (len(r) > 9 and int(r[9]) == 1) or not _rest:
                break
            _tier = _rest.pop(0)
            _st2, _no2, _fr2 = _TIERS[_tier]
            if os.environ.get("BRK_DEBUG") == "1":
                print("    brk: build refused at tier %d (%.1fs) -- stepping down to tier %d"
                      % (_tier - 1, time.time() - _pt, _tier), flush=True)
            # a coarser grid and fewer entry times: rebuild the column inputs for the new rung
            STEP, NOUT, NENT = _st2, _no2, _ne_of(_fr2)
            outs = outs[:NOUT]
            cand = list(res) + [b for _g, b in outs]
            isres = [True] * len(res) + [False] * len(outs)
            blocks_in = [(_layers_bbox(B, _b)[0], _layers_bbox(B, _b)[1], windows(_b))
                         for _b in cand]
            # the coarser rung offers DIFFERENT windows, so the per-seat prices are stale
            wts, winw = _price(cand, isres, blocks_in)
            warm = [w for w in (warm or []) if w[0] < len(cand)]
            _NCOL = _ncol_est(STEP, NOUT, NENT)
        finally:
            if _raised:
                _omp_threads(1)
        # the ratio is against what was ASKED, which is what the deflation has to undo
        _el = time.time() - _pt
        # AN ABORTED BUILD IS NOT AN ANSWER.  cranepack now projects its own O(ncol^2) build
        # from the rows it has finished and stops when the projection exceeds the cap, so a tier
        # that cannot be afforded costs the fraction already spent instead of the whole overrun.
        # The graph it leaves behind is missing edges, so any selection made over it could break
        # the crane rule -- the result is discarded outright rather than verified and hoped for.
        if len(r) > 9 and int(r[9]) == 1:
            if os.environ.get("BRK_DEBUG") == "1":
                print("    brk cost: BUILD ABORTED at %.1fs of a %.1fs cap (tier %d ncol~%.0f)"
                      % (_el, _cap, _tier, _NCOL), flush=True)
            return None
        _RATIO[0] = 0.5 * _RATIO[0] + 0.5 * (_el / max(1e-6, _ask))
        if os.environ.get("BRK_DEBUG") == "1":
            # A call is BUILD + SEARCH.  The search runs for as long as it is ASKED, which we
            # set; only the build is a property of the problem and has to be predicted.  The
            # first version of this trace was guarded by _tier >= 0 and so printed nothing on
            # the forced-knob path, which is exactly the path used to measure it.
            print("    brk cost: ncol~%.0f real_ncol=%s build=%.1fs ask=%.1fs total=%.1fs"
                  % (_NCOL, (r[2] if len(r) > 2 else "?"),
                     (float(r[4]) / 1000.0 if len(r) > 4 else -1.0), _ask, _el), flush=True)
        if _tier >= 0 and _NCOL > 0.0:
            # Seconds per squared column, fitted to the BUILD ONLY.
            #
            # The first version of this divided the WHOLE call by ncol^2, and that cost P3 its
            # entire gain: 90,475 where the same arm had given 86,665.  A call is build + solve,
            # the solve runs for as long as it is asked, and on a small tier the solve dominates
            # -- so charging all of it to ncol^2 inflates the rate, every larger tier then looks
            # unaffordable, and the operator can never climb off the tier it calibrated on.
            #
            # No estimate is needed: cranepack returns n_cols and build_ms in its result tuple.
            # The rate is fitted against OUR OWN column estimate rather than the returned count,
            # so the units match what the prediction above is computed from -- the estimate is an
            # upper bound (it counts positions the packer discards) and this absorbs that bias
            # instead of pretending it is not there.
            _build = float(r[4]) / 1000.0 if len(r) > 4 else _el
            _r = _build / (_NCOL * _NCOL)
            _PAIRRATE[0] = _r if _PAIRRATE[0] is None else 0.5 * _PAIRRATE[0] + 0.5 * _r
            # AND FEED IT BACK INTO THE FIT.  A real build at a real size is worth more than the
            # micro-builds the calibration could afford, and it is the only measurement taken at
            # the scale the prediction is actually made at.  The fixed cost is kept -- it is a
            # property of parsing the same blocks -- and the slope is re-derived from it.
            if _CALIB[1] is not None:
                _c0 = _CALIB[1][0]
                _rn = max(0.0, _build - _c0) / (_NCOL * _NCOL)
                if _rn > 0.0:
                    _CALIB[1] = (_c0, 0.5 * _CALIB[1][1] + 0.5 * _rn)
            if os.environ.get("BRK_DEBUG") == "1":
                print("    brk cost: tier %d ncol~%.0f real_ncol=%s build=%.1fs total=%.1fs"
                      "  -> rate %.4g s/col^2"
                      % (_tier, _NCOL, (r[2] if len(r) > 2 else "?"), _build, _el, _r), flush=True)
        # the 7th element is the bay, and it is present exactly when more than one was offered
        got = {int(p[0]): (int(p[1]), float(p[2]), float(p[3]), int(p[4]), int(p[5]),
                           BAYS[int(p[6])] if len(p) > 6 else TGT) for p in r[1]}

        # WHERE IT STOPS.  repack has seven exits that all look like None to the caller, and a
        # None tells you nothing about which one fired -- the directed and undirected variants
        # both returned None on a converged incumbent and the reason mattered more than the
        # result.  BRK_DEBUG names the exit.  Off by default and it changes no decision.
        _dbg = os.environ.get("BRK_DEBUG") == "1"

        def _say(msg):
            if _dbg:
                print("    brk[%s] bays=%s res=%d outs=%d %s"
                      % ("pressure", BAYS, len(res), len(outs), msg),
                      flush=True)

        # DID ANYTHING ACTUALLY MOVE.  This used to ask whether an OUTSIDER was admitted, which
        # is the right question when the pack covers one bay: nothing else can change there.
        # With two bays a resident of one that lands in the other has changed bay without being
        # an outsider, and that swap is precisely the move the joint neighbourhood was built to
        # find -- so the test is "some block ended up somewhere else", which is the same test
        # with one bay and the only one that admits the new move with two.
        admitted = [i for i in range(len(cand)) if not isres[i] and i in got]
        moved = [i for i in range(len(cand)) if i in got and got[i][5] != cur[cand[i]]]
        if not moved:
            _say("packer moved NO block between bays (seated %d of %d columns offered)"
                 % (len(got), len(cand)))
            return None
        # DISPLACED RESIDENTS.  An earlier version of this rejected any repack that failed to
        # re-seat every resident, on the reasoning that a partial repack needs somewhere to put
        # the leftovers.  That was measured wrong the moment the diagnostic ran: the repack that
        # took P3 from 96,990 to 82,175 re-seated 50 of 53 and displaced three, and the rule
        # would have thrown it away.  Trading a cheap resident out for an expensive entrant is
        # not a failure of the repack, it IS the repack -- and the weights already price it, so
        # cranepack drops the residents that cost least to lose.
        #
        # So rehome them instead, and make the engine say yes.  Each displaced block is offered
        # its bays in preference order and must find a legal seat at its own unchanged times
        # against the finished new state.  One that cannot is not "priced at its next-best bay"
        # -- that is the assumption the earlier diagnostics made and it is exactly the assumption
        # this whole night proved unsafe.  It kills the repack.
        # EVERY BLOCK ENDS UP IN EXACTLY ONE OF THREE PLACES.  Not a candidate -- which now
        # includes the residents frozen out of the window -- means it never moved.  A candidate
        # the packer seated takes the seat it was given.  A candidate it did not seat either stays
        # where it is (an outsider that was simply not admitted) or has to be rehomed (a resident
        # whose place was taken).  Stated this way rather than as a filter on the target bay,
        # because with a window there are now residents that are neither candidates nor movable.
        displaced = [i for i in range(len(cand)) if isres[i] and i not in got]
        _cset = set(cand)
        keep = {b: (cur[b], place[b][0], place[b][1], place[b][2], ent[b], ext[b])
                for b in range(n) if b not in _cset}
        for i, b in enumerate(cand):
            if i in got:
                o, x, y, en, ex, jb = got[i]
                keep[b] = (jb, int(o), float(x), float(y), int(en), int(ex))
            elif not isres[i]:
                keep[b] = (cur[b], place[b][0], place[b][1], place[b][2], ent[b], ext[b])
        if displaced:
            if engine_fn is None:
                return None
            E = engine_fn(prob_info)
            E.clear_all()
            for q, (j, o, x, y, en, ex) in keep.items():
                E.add(int(j), int(q), int(o), float(x), float(y), int(en), int(ex))
            # REHOMING MAY MOVE THE CLOCK, NOT ONLY THE BAY.
            #
            # This step used to demand a seat at the block's OWN UNCHANGED entry and exit, in some
            # other bay, and killed the whole repack when it could not find one.  Measured, that
            # is where the operator actually dies -- three instances, three different bay counts,
            # every one of them the same line:
            #
            #     P3   one bay  built 7.0 s, searched 44 s -> displaced b63  could not be rehomed
            #     P20  one bay  built 15.4 s, searched 87 s -> displaced b14  could not be rehomed
            #     P3   two bays built 0.6 s, searched 50 s -> displaced b194 could not be rehomed
            #
            # In each case the packer HAD a better arrangement and it was thrown away at the
            # legalisation step, over one block.  The packer's model is what makes this happen: it
            # prices seating a block and is free to leave the cheapest one out, but the problem
            # does not allow a block to be left out -- so the block it dropped has to go somewhere,
            # and demanding the same day as well as a different bay is a harder question than the
            # objective ever asks.
            #
            # Lateness is PRICED, not forbidden: w1 per day of tardiness, and the rebuilt solution
            # is scored by the real grader before it is returned.  So try the block's own time
            # first -- across every bay, since a free move is always better -- and only then walk
            # the entry forward a day at a time.  Never earlier: that could breach release_time,
            # which is a constraint rather than a cost.  A repack that pays for the delay survives
            # the final comparison and one that does not is still rejected, so the bound on the
            # walk is about cost, not about safety.
            # EVERY BAY, INCLUDING THE ONES JUST REPACKED.  Excluding them looked safe -- the
            # packer had, after all, just declined to seat this block there -- but it declined on
            # a COARSE grid, and feasible_scan works on the real one against the finished new
            # state.  There is no reason a seat it could not see must not exist, and forbidding it
            # cost the whole repack over one block.  Preference order, which is what the objective
            # asks for; the engine still has to agree and the grader still has to agree after it.
            _order2 = list(range(m))
            _RETRY = max(1, int(os.environ.get("OGC_BRKRETRY", "16")))
            # HARDEST FIRST.  Rehoming is sequential and each block that lands becomes an obstacle
            # for the next, so the order is not a detail: a small block placed early can take the
            # only opening a large one had.  Largest footprint first is the standard remedy and it
            # costs nothing to apply.  The trace names the whole displaced set, because "one block
            # could not be rehomed" does not say whether the yard is full or the order was wrong.
            _area = {}
            for i in displaced:
                _b2 = cand[i]
                _, _ob3 = _layers_bbox(B, _b2)
                _area[i] = max((_q[2] - _q[0]) * (_q[3] - _q[1]) for _q in _ob3)
            displaced.sort(key=lambda i: -_area[i])
            _say("displaced %d: %s" % (len(displaced),
                                       [(cand[i], int(_area[i])) for i in displaced]))

            # FIRST-FAIL-FIRST, because the order is what fails and not the yard.  Largest-first
            # is a good guess and it is only a guess: on P3 it seated b177 (420) and b31 (414) and
            # then could not seat b101 (253), so the opening b101 needed had been taken by a
            # SMALLER block placed earlier.  When a block cannot be seated, put it at the front and
            # start the whole rehoming again from the post-pack state -- the classic repair for a
            # sequential placement that is sensitive to order, and cheap here because a pass is
            # only feasible_scan calls against a C++ engine.  Bounded by the number of displaced
            # blocks, so it terminates; each pass promotes a block that has never been promoted.
            _base_state = dict(keep)

            def _rehome_from(_state):
                """Seat every displaced block against _state, retrying the order when one sticks.
                Returns the completed placement dict, or None."""
                _front, _seen = [], set()
                _placed = None
                for _pass in range(1 + len(displaced)):
                    keep = dict(_state)
                    E.clear_all()
                    for q, (j, o, x, y, en, ex) in keep.items():
                        E.add(int(j), int(q), int(o), float(x), float(y), int(en), int(ex))
                    _ordD = _front + [i for i in displaced if i not in set(_front)]
                    _fail = None
                    for i in _ordD:
                        b = cand[i]
                        seated = False
                        _bo = sorted(_order2, key=lambda k: -pref[b][k])
                        for _d in range(_RETRY):
                            _en, _ex = ent[b] + _d, ext[b] + _d
                            for j in _bo:
                                rr = E.feasible_scan(int(b), [int(j)], int(_en), int(_ex), 1)
                                if len(rr):
                                    E.add(int(j), int(b), int(rr[0][1]), float(rr[0][2]),
                                          float(rr[0][3]), int(_en), int(_ex))
                                    keep[b] = (j, int(rr[0][1]), float(rr[0][2]),
                                               float(rr[0][3]), _en, _ex)
                                    seated = True
                                    break
                            if seated:
                                break
                        if not seated:
                            _fail = i
                            break
                    if _fail is None:
                        _placed = keep
                        break
                    if _fail in _seen:
                        break                   # promoting it again would repeat this pass
                    _seen.add(_fail)
                    _front = [_fail] + _front
                return _placed

            # A FAILED REHOMING IS NOT A DEAD END.  GIVE A SEAT BACK.
            #
            # It is the operator's single largest exit -- eight of thirty-two calls in the census
            # in results/audit/brkexit.log, and forty percent of the calls where the packer
            # actually produced an arrangement.  Every one of those threw away a legal, better
            # packing over one block, after the build and the search had already been paid for.
            #
            # The cause is in the packer's model rather than in the search.  It prices seating a
            # block and is free to leave the cheapest one out, but the problem does not allow a
            # block to be left out.  When the block it dropped then has nowhere to go, the trade
            # it made was not actually available.
            #
            # So undo the cheapest part of that trade instead of all of it.  Admitted outsiders
            # can ALWAYS be returned: an outsider's home bay is outside the repacked set, nothing
            # in that bay moved, so its incumbent seat is exactly as free as it was.  Give back
            # the least valuable one, which frees its space in the repacked bay, and try again.
            # Repeat while seats remain to give.  In the limit every admitted block goes home and
            # the result is the incumbent, so this terminates and can never be worse -- the final
            # comparison still rejects anything that does not pay.
            _placed = _rehome_from(_base_state)
            _gave = 0
            if _placed is None:
                _order_cheap = sorted(admitted, key=lambda i: wts[i])
                for _i0 in _order_cheap:
                    _b0 = cand[_i0]
                    _base_state[_b0] = (cur[_b0], place[_b0][0], place[_b0][1], place[_b0][2],
                                        ent[_b0], ext[_b0])
                    _gave += 1
                    _placed = _rehome_from(_base_state)
                    if _placed is not None:
                        break
            if _placed is None:
                _say("displaced blocks could not be rehomed even after giving back all %d seats"
                     % len(admitted))
                return None
            if _gave:
                _say("gave back %d of %d admitted seats to rehome the displaced" % (_gave, len(admitted)))
            keep = _placed
        if len(keep) != n:
            _say("rebuilt %d of %d blocks" % (len(keep), n))
            return None
        recs = [{"block_id": b, "bay_id": j, "orient_idx": o, "x": x, "y": y,
                 "entry_time": en, "exit_time": ex}
                for b, (j, o, x, y, en, ex) in sorted(keep.items())]
        out = build_fn(recs)
        o, _c = total_fn(prob_info, out)
        # o is +inf when the grader refuses the rebuild, and int(inf) raises -- which turned a
        # rejected repack into an exception that the blanket catch then reported as an ordinary
        # None.  The trace has to survive the case it exists to describe.
        _say("admitted %d, moved %d, displaced %d, obj %s vs base %d -> %s"
             % (len(admitted), len(moved), len(displaced),
                ("%.0f" % o) if o < float("inf") else "INFEASIBLE", int(base),
                "KEEP" if o < base - 1e-9 else "reject"))
        return out if o < base - 1e-9 else None
    except Exception:
        # The blanket catch is deliberate -- an operator must never take the run down -- but it
        # has hidden a real fault once already this session (an engine signature change raised
        # TypeError in here and four queues reported the greedy floor as an ordinary result).
        if os.environ.get("BRK_DEBUG") == "1":
            import traceback
            traceback.print_exc()
        return None

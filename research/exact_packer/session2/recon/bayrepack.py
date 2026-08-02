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
_TIERS = [(4, 40, 1.0), (4, 40, 0.5), (4, 20, 1.0 / 3.0), (6, 10, 1.0 / 6.0)]
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


def repack(prob_info, sol, budget, total_fn, build_fn, engine_fn=None,
           nout=None, step=None, nent=None, hard=None):
    """One repack of the most contested bay.  Returns a better operations dict, or None.

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
        wts = []
        for i, b in enumerate(cand):
            fall = (min((j for j in range(m) if j != TGT),
                        key=lambda j: pref[b][TGT] - pref[b][j]) if isres[i] else cur[b])
            if isres[i]:
                alt = list(cur); alt[b] = fall
                wts.append(max(1.0, obj_of(alt, ent, ext) - base))
            else:
                wts.append(float(outs[i - len(res)][0]))

        warm = [(i, place[b][0], int(place[b][1]), int(place[b][2]))
                for i, b in enumerate(cand) if isres[i]]
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
            _cap = (float(hard) if hard is not None else SL) * 0.85
            _ask = max(_MINASK, _cap)
        _pt = time.time()
        r = CP.pack(blocks_in, W, H, STEP, _ask,
                    seed=12345 + 7919 * k, warm=warm or None, frozen=[],
                    weights=[float(x) for x in wts],
                    total_s=_cap)
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
            if os.environ.get("BRK_DEBUG") == "1":
                print("    brk cost: tier %d ncol~%.0f real_ncol=%s build=%.1fs total=%.1fs"
                      "  -> rate %.4g s/col^2"
                      % (_tier, _NCOL, (r[2] if len(r) > 2 else "?"), _build, _el, _r), flush=True)
        got = {loc: (o, x, y, en, ex) for (loc, o, x, y, en, ex) in r[1]}

        # WHERE IT STOPS.  repack has seven exits that all look like None to the caller, and a
        # None tells you nothing about which one fired -- the directed and undirected variants
        # both returned None on a converged incumbent and the reason mattered more than the
        # result.  BRK_DEBUG names the exit.  Off by default and it changes no decision.
        _dbg = os.environ.get("BRK_DEBUG") == "1"

        def _say(msg):
            if _dbg:
                print("    brk[%s] tgt=%d res=%d outs=%d %s"
                      % ("wish" if wcands else "pressure", TGT, len(res), len(outs), msg),
                      flush=True)

        admitted = [i for i in range(len(cand)) if not isres[i] and i in got]
        if not admitted:
            _say("packer admitted NO outsider (seated %d of %d columns offered)"
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
        displaced = [i for i in range(len(cand)) if isres[i] and i not in got]
        keep = {b: (cur[b], place[b][0], place[b][1], place[b][2], ent[b], ext[b])
                for b in range(n) if cur[b] != TGT and b not in {cand[i] for i in admitted}}
        for i, b in enumerate(cand):
            if i in got:
                o, x, y, en, ex = got[i]
                keep[b] = (TGT, int(o), float(x), float(y), int(en), int(ex))
        if displaced:
            if engine_fn is None:
                return None
            E = engine_fn(prob_info)
            E.clear_all()
            for q, (j, o, x, y, en, ex) in keep.items():
                E.add(int(j), int(q), int(o), float(x), float(y), int(en), int(ex))
            for i in displaced:
                b = cand[i]
                seated = False
                for j in sorted((k for k in range(m) if k != TGT), key=lambda k: -pref[b][k]):
                    r = E.feasible_scan(int(b), [int(j)], int(ent[b]), int(ext[b]), 1)
                    if len(r):
                        E.add(int(j), int(b), int(r[0][1]), float(r[0][2]), float(r[0][3]),
                              int(ent[b]), int(ext[b]))
                        keep[b] = (j, int(r[0][1]), float(r[0][2]), float(r[0][3]),
                                   ent[b], ext[b])
                        seated = True
                        break
                if not seated:
                    _say("displaced b%d could not be rehomed in any other bay" % b)
                    return None
        if len(keep) != n:
            _say("rebuilt %d of %d blocks" % (len(keep), n))
            return None
        recs = [{"block_id": b, "bay_id": j, "orient_idx": o, "x": x, "y": y,
                 "entry_time": en, "exit_time": ex}
                for b, (j, o, x, y, en, ex) in sorted(keep.items())]
        out = build_fn(recs)
        o, _c = total_fn(prob_info, out)
        _say("admitted %d, displaced %d, obj %d vs base %d -> %s"
             % (len(admitted), len(displaced), int(o), int(base),
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

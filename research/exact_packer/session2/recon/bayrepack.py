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
# The packer's runtime is a property of the PROBLEM, not of the deadline it is given -- measured
# on P3, every large-tier call took 77-81 s whether it was asked for 35 s or 100 s, and every
# small-tier call about 20 s.  So the tiers are listed largest-first with their measured cost,
# and the operator takes the largest one the remaining time can absorb.  Costs are updated from
# what actually happens, so a different machine or instance corrects the seed rather than
# inheriting it.
_TIERS = [(4, 40, 3), (4, 20, 2), (6, 10, 1)]
_TIERCOST = [80.0, 21.0, 21.0]


_WISH_CACHE = {}


def _wish(cur, wl, pref, mxp, u, m, n, K, tl, w2, w3):
    """Which blocks would an EXACT reassignment move, if geometry were free?

    WHY THE OPERATOR NEEDS ASKING.  Outsiders are ranked below by their own SINGLE-move gain --
    move b to the target bay, keep everything else, see if the objective drops.  That is the
    right price for one block and the wrong price for a SET, because Z2 is a RANGE: moving one
    block off the extreme bay only helps until another bay becomes the extreme, so
    individually-profitable moves stop paying together, and jointly-profitable ones can each
    look worthless alone.  A greedy ranking cannot see either case.

    Measured on P3 (harness/masterprobe3.py) -- best assignment within a Hamming ball of the
    incumbent, geometry ignored, entry times pinned:

        K=1  79,492      K=2  72,438      K=3  65,426      K=4  59,292      K=16  36,759

    From 86,665 a single move is worth 8.3% and three are worth 24.5%, and K=16 lands on the
    capacity-aware bound to six digits.  So the moves worth making are few, they are nameable,
    and masterprobe2 showed they are refused by the PACKER rather than missed by the model --
    which is this operator's entire job description.

    Returns the wished ASSIGNMENT; the caller prices it with its own obj_of, so this module
    still never decides what "better" means.  Geometry is deliberately absent: a wish the packer
    cannot seat costs one refused column, while a wish suppressed in advance cannot be tried at
    all.  None if OR-Tools is missing or the solve does not land, and the caller then falls back
    to the single-move ranking it has always used.

    Cached on the assignment, because the allocator calls the operator repeatedly and the wish
    only changes when the incumbent does.
    """
    key = (tuple(cur), K)
    if key in _WISH_CACHE:
        return _WISH_CACHE[key]
    try:
        from ortools.sat.python import cp_model
    except Exception:
        return None
    SC = 1000
    U = [int(round(SC * u[j])) for j in range(m)]
    mdl = cp_model.CpModel()
    x = [[mdl.NewBoolVar("x%d_%d" % (b, j)) for j in range(m)] for b in range(n)]
    for b in range(n):
        mdl.Add(sum(x[b]) == 1)
    mdl.Add(sum(1 - x[b][cur[b]] for b in range(n)) <= K)
    ld = [mdl.NewIntVar(0, 10 ** 9, "l%d" % j) for j in range(m)]
    for j in range(m):
        mdl.Add(ld[j] == sum(x[b][j] * int(round(wl[b])) for b in range(n)))
    Mv = mdl.NewIntVar(0, 10 ** 12, "M")
    for j in range(m):
        for j2 in range(m):
            if j != j2:
                mdl.Add(Mv >= U[j] * ld[j] - U[j2] * ld[j2])
    # Mv/SC is the load range Z2 floors, so this is SC times w2*Z2 + w3*Z3 -- the objective
    # obj_of computes, minus the w1*Z1 term that the pinned entry times hold constant.
    mdl.Minimize(w2 * Mv + w3 * SC * sum(x[b][j] * (mxp[b] - pref[b][j])
                                         for b in range(n) for j in range(m)))
    for b in range(n):
        for j in range(m):
            mdl.AddHint(x[b][j], 1 if cur[b] == j else 0)
    slv = cp_model.CpSolver()
    slv.parameters.max_time_in_seconds = max(0.5, float(tl))
    slv.parameters.num_search_workers = 1
    st = slv.Solve(mdl)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        _WISH_CACHE[key] = None
        return None
    want = [next(j for j in range(m) if slv.Value(x[b][j]) == 1) for b in range(n)]
    _WISH_CACHE[key] = want
    return want


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
        _ev = (os.environ.get("BRK_STEP"), os.environ.get("BRK_NOUT"), os.environ.get("BRK_NENT"))
        SL = float(budget)
        if step is None and nout is None and nent is None and not any(_ev):
            # (step, nout, nent) largest first; _TIERCOST[i] is its measured seconds
            # The run's remaining time is the real constraint; the slice is advisory and the
            # packer overruns it by construction.  Without `hard` the operator cannot tell 40 s
            # of slice with 190 s left from 40 s of slice with 45 s left, and those want
            # opposite tiers.  0.85 leaves room for the rehoming scans and the grader check that
            # follow the pack.
            if os.environ.get("BRK_OLDTIER") == "1":
                # The rule this replaced, kept switchable so the two can be measured against
                # each other INSIDE ONE QUEUE.  Arm levels have drifted between queues twice
                # tonight, so a fix cannot be scored against numbers from an earlier queue --
                # which is the only comparison available otherwise, and it is not a comparison.
                _eff = SL / max(1.0, _RATIO[0])
                if _eff < 15.0:
                    STEP, NOUT, NENT = 6, 10, 1
                elif _eff < 40.0:
                    STEP, NOUT, NENT = 4, 20, 2
                else:
                    STEP, NOUT, NENT = 4, 40, 3
                _tier = -1
            else:
                _cap = (float(hard) if hard is not None else SL) * 0.85
                for _ti, (_st, _no, _ne) in enumerate(_TIERS):
                    if _TIERCOST[_ti] <= _cap or _ti == len(_TIERS) - 1:
                        STEP, NOUT, NENT = _st, _no, _ne
                        _tier = _ti
                        break
        else:
            STEP = int(step if step is not None else (_ev[0] or 4))
            NOUT = int(nout if nout is not None else (_ev[1] or 40))
            NENT = int(nent if nent is not None else (_ev[2] or 3))
            _tier = -1

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
        # BRK_TARGET pins the bay, so an exhaustive sweep can cover every one of them instead
        # of re-picking the most-pressed each call.  Unset -- which is every path the pipeline
        # takes -- leaves the measured choice untouched.
        _tg = os.environ.get("BRK_TARGET")
        _order = ([int(_tg)] if _tg is not None and _tg.isdigit() and int(_tg) < m
                  else sorted(range(m), key=lambda j: -(u[j] * sum(wl[b] for b in range(n)
                                                                   if cur[b] == j))))
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
                cands.append((j, got_outs[:NOUT]))
                break
        # DIRECTED VARIANT.  With BRK_WISH the target bay and the outsider list come from an
        # exact reassignment rather than from pressure and single-move gain -- see _wish for why
        # a single-move ranking cannot price a set when Z2 is a range.  Wished blocks are priced
        # by leave-one-out INSIDE the wish, so an outsider's weight and a resident's eviction
        # cost stay the same currency.  The single-move list for the same bay is appended after
        # them, so the candidate pool is never smaller than the undirected operator's.  If the
        # solve does not land, or wants nothing, this falls through untouched.
        wcands = []
        if os.environ.get("BRK_WISH") == "1":
            _want = _wish(cur, wl, pref, mxp, u, m, n, NOUT,
                          min(3.0, max(0.5, SL * 0.10)), w2, w3)
            if _want is not None:
                _wo = obj_of(_want, ent, ext)
                if _wo < base - 1e-9:
                    byb = {}
                    for b in range(n):
                        if _want[b] != cur[b]:
                            alt = list(_want); alt[b] = cur[b]
                            byb.setdefault(_want[b], []).append(
                                (max(1.0, obj_of(alt, ent, ext) - _wo), b))
                    for j in sorted(byb, key=lambda j: -sum(g for g, _ in byb[j])):
                        if any(cur[b] == j for b in range(n)):
                            wcands.append((j, sorted(byb[j], reverse=True)))
        if wcands:
            TGT, outs = wcands[0]
            _have = {b for _, b in outs}
            for _j, _lst in cands:            # top up from the single-move ranking, same bay
                if _j == TGT:
                    outs = outs + [(g, b) for g, b in _lst if b not in _have]
            outs = outs[:NOUT]
        elif cands:
            TGT, outs = cands[0]
        else:
            return None                       # no bay has a profitable entrant anywhere
        res = [b for b in range(n) if cur[b] == TGT]

        W, H = float(bays[TGT]["width"]), float(bays[TGT]["height"])

        def windows(b):
            """Entry times to offer.  Restricted to the tardiness-free window so a repack can
            never CREATE lateness; if the block is already unavoidably late (window empty, which
            is the saturated case) it keeps the time it has and only its position is free."""
            lo, hi = rel[b], due[b] - pt[b]
            if hi < lo:
                return [(ent[b], ent[b] + pt[b])]
            ts = {lo, hi}
            if lo <= ent[b] <= hi:
                ts.add(ent[b])
            for i in range(max(1, NENT)):
                ts.add(lo + (hi - lo) * i // max(1, NENT - 1) if NENT > 1 else lo)
            return [(t, t + pt[b]) for t in sorted(ts)]

        cand = list(res) + [b for _, b in outs]
        isres = [True] * len(res) + [False] * len(outs)
        blocks_in = []
        for b in cand:
            ol, ob = _layers_bbox(B, b)
            blocks_in.append((ol, ob, windows(b)))

        wts = []
        for i, b in enumerate(cand):
            if isres[i]:
                alt = list(cur)
                alt[b] = min((j for j in range(m) if j != TGT),
                             key=lambda j: pref[b][TGT] - pref[b][j])
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
        _pt = time.time()
        r = CP.pack(blocks_in, W, H, STEP, _ask,
                    seed=12345 + 7919 * k, warm=warm or None, frozen=[],
                    weights=[float(x) for x in wts])
        # the ratio is against what was ASKED, which is what the deflation has to undo
        _el = time.time() - _pt
        _RATIO[0] = 0.5 * _RATIO[0] + 0.5 * (_el / max(1e-6, _ask))
        if _tier >= 0:
            _TIERCOST[_tier] = 0.5 * _TIERCOST[_tier] + 0.5 * _el
        got = {loc: (o, x, y, en, ex) for (loc, o, x, y, en, ex) in r[1]}

        admitted = [i for i in range(len(cand)) if not isres[i] and i in got]
        if not admitted:
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
                    return None
        if len(keep) != n:
            return None
        recs = [{"block_id": b, "bay_id": j, "orient_idx": o, "x": x, "y": y,
                 "entry_time": en, "exit_time": ex}
                for b, (j, o, x, y, en, ex) in sorted(keep.items())]
        out = build_fn(recs)
        o, _c = total_fn(prob_info, out)
        return out if o < base - 1e-9 else None
    except Exception:
        return None

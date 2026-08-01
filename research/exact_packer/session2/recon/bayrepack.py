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
           nout=None, step=None, nent=None):
    """One repack of the most contested bay.  Returns a better operations dict, or None.

    total_fn(prob_info, sol) -> (objective, checkdict)   the caller's own scorer, so this
    module never decides what "better" means.
    build_fn(list of assignment records) -> operations dict
    engine_fn(prob_info) -> ogc_fast Engine, used to rehome blocks the repack displaces.
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

        # SIZE THE PROBLEM TO THE SLICE, because the packer will not size itself to the clock.
        #
        # cranepack's time_budget_s is not a hard limit.  Measured on this instance: the same
        # call at grid step 4 returned inside its 120 s, and at step 2 -- four times the position
        # grid -- it ran 18 minutes against the same 120 s ask.  A 9x overrun.  Inside a
        # diagnostic that is a blocked queue; inside the operator, at the grader's hard limit, it
        # is a missing answer.
        #
        # There is no knob that makes it stop, so the defence is to hand it a problem whose size
        # is bounded rather than a deadline it ignores.  Three levers set the column count --
        # positions per orientation (STEP), candidate blocks (NOUT), entry times each (NENT) --
        # and all three shrink together when the slice is short.  This is fitting the work to the
        # time available, not a threshold on any property of the instance.
        #
        # The tiers are chosen against an EFFECTIVE slice, not the one asked for, because a fixed
        # table would just be my guess at the overrun.  The operator measures its own: the first
        # smoke test asked 60 s at the largest tier and took 115.5 s, so the ratio is real and
        # it is not 1.  Dividing the slice by the running ratio makes the next call pick a tier
        # that fits the time actually available on THIS machine and THIS instance, and the
        # estimate is blended rather than replaced so one slow call does not collapse it.
        # An explicit argument or env override wins over the tiers, so a sweep can ask for a
        # size the tier table would never pick.  Without this the env vars read as live knobs
        # and are silently ignored, which is the same class of quiet failure as a knob that
        # reaches the call site but not the signature.
        _ev = (os.environ.get("BRK_STEP"), os.environ.get("BRK_NOUT"), os.environ.get("BRK_NENT"))
        SL = float(budget)
        if step is None and nout is None and nent is None and not any(_ev):
            eff = SL / max(1.0, _RATIO[0])
            if eff < 15.0:
                STEP, NOUT, NENT = 6, 10, 1
            elif eff < 40.0:
                STEP, NOUT, NENT = 4, 20, 2
            else:
                STEP, NOUT, NENT = 4, 40, 3
        else:
            STEP = int(step if step is not None else (_ev[0] or 4))
            NOUT = int(nout if nout is not None else (_ev[1] or 40))
            NENT = int(nent if nent is not None else (_ev[2] or 3))

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
        cands = []
        for j in sorted(range(m), key=lambda j: -(u[j] * sum(wl[b] for b in range(n)
                                                             if cur[b] == j))):
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
        if not cands:
            return None                       # no bay has a profitable entrant anywhere
        TGT, outs = cands[0]
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
        _RATIO[0] = 0.5 * _RATIO[0] + 0.5 * ((time.time() - _pt) / max(1e-6, _ask))
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

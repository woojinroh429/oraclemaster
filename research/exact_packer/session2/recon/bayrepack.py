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

WHY IT IS NOT A P3 SPECIAL CASE.  The contested bay is chosen by measurement -- the bay whose
u_j * load_j is highest, which is the one setting Z2's maximum and, on every instance measured,
also the one that turns blocks away.  On a saturated instance the same operator buys Z1 instead
of Z3: a bay that packs better admits blocks earlier and fewer of them are late.  Nothing here
tests density, and nothing is tuned to one instance.

SAFETY.  The rebuilt solution is verified with the real grader before it is returned, and a
repack that fails to re-seat every resident is discarded rather than patched -- a partial
repack would need a home for the displaced blocks, which is a second search and a second way to
be wrong.  Returning None always means the caller keeps what it had.
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


def repack(prob_info, sol, budget, total_fn, build_fn, nout=None, step=None, nent=None):
    """One repack of the most contested bay.  Returns a better operations dict, or None.

    total_fn(prob_info, sol) -> (objective, checkdict)   the caller's own scorer, so this
    module never decides what "better" means.
    build_fn(list of assignment records) -> operations dict
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
        # THE CONTESTED BAY: the one setting Z2's maximum.  Measured, not named -- on a
        # saturated instance this is the bay whose refusals turn into tardiness instead of
        # preference, and the operator is the same either way.
        v0 = [u[j] * sum(wl[b] for b in range(n) if cur[b] == j) for j in range(m)]
        TGT = max(range(m), key=lambda j: v0[j])
        res = [b for b in range(n) if cur[b] == TGT]
        if not res:
            return None

        # outsiders, priced exactly against the incumbent
        NOUT = int(nout if nout is not None else os.environ.get("BRK_NOUT", "40"))
        outs = []
        for b in range(n):
            if cur[b] == TGT:
                continue
            alt = list(cur); alt[b] = TGT
            g = base - obj_of(alt, ent, ext)
            if g > 0:
                outs.append((g, b))
        outs.sort(reverse=True)
        outs = outs[:NOUT]
        if not outs:
            return None                       # nothing wants in; a repack cannot pay

        W, H = float(bays[TGT]["width"]), float(bays[TGT]["height"])
        STEP = int(step if step is not None else os.environ.get("BRK_STEP", "4"))
        NENT = int(nent if nent is not None else os.environ.get("BRK_NENT", "3"))

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
        r = CP.pack(blocks_in, W, H, STEP, max(1.0, float(budget) - (time.time() - t0)),
                    seed=12345, warm=warm or None, frozen=[],
                    weights=[float(x) for x in wts])
        got = {loc: (o, x, y, en, ex) for (loc, o, x, y, en, ex) in r[1]}

        # every resident must come back.  A partial repack would need somewhere to put the
        # displaced, which is a second search and a second way to be wrong.
        if any(isres[i] and i not in got for i in range(len(cand))):
            return None
        admitted = [i for i in range(len(cand)) if not isres[i] and i in got]
        if not admitted:
            return None

        recs = []
        for b in range(n):
            if cur[b] == TGT or b in [cand[i] for i in admitted]:
                continue
            oi, x, y = place[b]
            recs.append({"block_id": b, "bay_id": cur[b], "orient_idx": oi, "x": x, "y": y,
                         "entry_time": ent[b], "exit_time": ext[b]})
        for i, b in enumerate(cand):
            if i not in got:
                continue
            o, x, y, en, ex = got[i]
            recs.append({"block_id": b, "bay_id": TGT, "orient_idx": int(o), "x": int(x),
                         "y": int(y), "entry_time": int(en), "exit_time": int(ex)})
        if len(recs) != n:
            return None
        out = build_fn(recs)
        o, _c = total_fn(prob_info, out)
        return out if o < base - 1e-9 else None
    except Exception:
        return None

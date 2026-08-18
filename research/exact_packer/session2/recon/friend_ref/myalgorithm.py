# -*- coding: utf-8 -*-
# myalgorithm.py -- OGC2026 entry point (submission v12)
#
# Single gate-free engine (no instance classification):
#   Construct  4 parallel workers (conservative/TIGHT raster x beam-width
#              ladder x future-value beta) race on every instance; each
#              worker is a beam search over ALL bays x orientations x
#              integer positions (numba raster + fused sweep), candidates
#              ranked by the true objective delta, beam kept diverse by a
#              per-parent quota and pruned by an admissible obj2 bound.
#              Each worker's ladder rung 2 (fires when rung 1 finishes
#              early, i.e. small/mid instances) runs the pure conservative
#              line (edd_big, beta 0) the beta-carrying matrix lost in v6.
#   Improve    time_repair (single + batch-ruin LNS with adaptive operator
#              weights) and bay-flip rebalance alternate until the deadline.
#   Safety     spawn canary (falls back to full-budget sequential),
#              tail-aware emergency guard, always-feasible fallback
#              solution, final exact-objective validation.

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ============================================================
# ENV SWITCH INVENTORY  (submission self-check -- see _assert_defaults)
#
# The engine reads OGC_* environment switches in three classes:
#   POLICY     -- define the submitted behaviour; set by THIS file or
#                 carrying measured defaults (documented in the roadmap
#                 constants table): OGC_S=2, OGC_NATIVE=1, OGC_TIGHT
#                 (per-worker), OGC_KCLATE=3.0, OGC_KCOST=6e-6,
#                 OGC_MORTON=on, OGC_VERIFY_TRIES=12, OGC_TRISW=1,
#                 OGC_TRITHR=0.9, OGC_TRIMULT=2.0, OGC_TRIREL=0.2,
#                 OGC_TRIR2=1, OGC_POSP=1.
#   DIAGNOSTIC -- logging only, provably behaviour-invariant:
#                 OGC_DEBUG, OGC_LOOPLOG, OGC_T4LOG, OGC_KC, OGC_ALNSSEG.
#   LOCAL A/B  -- experiment scaffolding kept for reproducibility of the
#                 measurement log; every switch below defaults to the
#                 submitted path and the unset state IS the submission.
# ============================================================
_AB_SCAFFOLD = {
    # name: default-equivalent unset value.  A switch is "off" (submitted
    # path) when unset or equal to this value.
    "OGC_NOESH": "0", "OGC_ESH": "0", "OGC_DISP": "0", "OGC_DISPW": "",
    "OGC_DISPS": "", "OGC_ELIT": "0", "OGC_EPR": "0", "OGC_EPRW": "",
    "OGC_EPK": "0", "OGC_ECT": "0", "OGC_EAL": "0", "OGC_EALW": "",
    "OGC_MERGE": "0", "OGC_NOT1": "0", "OGC_NOT4": "0", "OGC_NOT5": "0",
    "OGC_NOS2": "0", "OGC_NOS5": "0", "OGC_NOC3": "0", "OGC_T2": "0",
    "OGC_POSDIV": "0", "OGC_ORIDIV": "0", "OGC_PKRUNG": "",
    "OGC_PRDRIFT": "0", "OGC_SWK4": "0", "OGC_BITPACK": "0",
    "OGC_WIDTHMUL": "", "OGC_WBUDGET": "", "OGC_WDEADLINE": "",
    "OGC_TIGHT_T": "",
}


def _assert_defaults():
    """Submission-path self check: report any local-A/B scaffolding switch
    that is set away from the submitted default.  Behaviour-invariant --
    it only prints (under OGC_DEBUG) and returns a bool."""
    off = [k for k, d in _AB_SCAFFOLD.items()
           if os.environ.get(k) not in (None, "", d)]
    if off and os.environ.get("OGC_DEBUG") == "1":
        print("WARN non-default A/B switches:", off, flush=True)
    return not off


def _build_ops_safe(assignments):
    """Self-contained copy of gridsolver._build_operations so the safety
    net has ZERO import dependencies (numba/scipy/shapely failures must
    not be able to take the fallback down with them)."""
    buckets = {}
    for a in assignments:
        buckets.setdefault(int(a["exit_time"]), []).append(
            (0, "EXIT", a["block_id"], a["bay_id"], None, None, None))
        buckets.setdefault(int(a["entry_time"]), []).append(
            (1, "ENTRY", a["block_id"], a["bay_id"],
             a["x"], a["y"], a["orient_idx"]))
    operations = {}
    for t in sorted(buckets):
        ops = sorted(buckets[t], key=lambda x: (x[0], x[2]))
        out = []
        for _, kind, bid, bay, x, y, oi in ops:
            op = {"type": kind, "block_id": bid, "bay_id": bay}
            if kind == "ENTRY":
                op.update(x=x, y=y, orient_idx=oi)
            out.append(op)
        operations[str(t)] = out
    return operations


def _fallback_solution(prob_info):
    """Guaranteed-feasible solution in O(n): every block gets an exclusive
    empty-bay time window (bay empty at its entry and exit -> the crane
    checks trivially pass), placed at its exact bbox corner in the first
    (preference-ordered) bay+orientation that fits.  Used only as a safety
    net when the main pipeline fails or the budget is blown."""
    bays = prob_info["bays"]
    blocks = prob_info["blocks"]
    n_bays = len(bays)
    bay_free = [0] * n_bays  # earliest time the bay is completely free
    assignments = []
    order = sorted(range(len(blocks)),
                   key=lambda i: (blocks[i]["release_time"],
                                  blocks[i]["due_date"]))
    for bi in order:
        bd = blocks[bi]
        chosen = None
        for bay_id in sorted(range(n_bays),
                             key=lambda j: -bd["bay_preferences"][j]):
            for oi, sh in enumerate(bd["shape"]):
                vs = [v for layer in sh["layers"] for v in layer]
                xs = [v[0] for v in vs]
                ys = [v[1] for v in vs]
                w, h = max(xs) - min(xs), max(ys) - min(ys)
                if w <= bays[bay_id]["width"] + 1e-9 \
                        and h <= bays[bay_id]["height"] + 1e-9:
                    import math
                    # the checker maps (x, y) onto the REFERENCE point
                    # (first vertex of layer 0) and rounds to int, so the
                    # slot must be an INTEGER in [ref-min, DIM-max+ref].
                    # The old form assumed ref==(0,0) and never checked
                    # the far edge -> every fallback solution was stage-2
                    # infeasible (measured 0/40).
                    ref_x, ref_y = sh["layers"][0][0]
                    lo_x = ref_x - min(xs)
                    hi_x = bays[bay_id]["width"] - max(xs) + ref_x
                    lo_y = ref_y - min(ys)
                    hi_y = bays[bay_id]["height"] - max(ys) + ref_y
                    px = math.ceil(lo_x - 1e-9)
                    py = math.ceil(lo_y - 1e-9)
                    if px > hi_x + 1e-9 or py > hi_y + 1e-9:
                        continue  # no integer slot in this orientation
                    chosen = (bay_id, oi, px, py)
                    break
            if chosen:
                break
        bay_id, oi, px, py = chosen
        entry = max(int(bd["release_time"]), bay_free[bay_id])
        exit_t = entry + int(bd["processing_time"])
        bay_free[bay_id] = exit_t
        assignments.append({"block_id": bi, "bay_id": bay_id, "x": px,
                            "y": py, "orient_idx": oi, "entry_time": entry,
                            "exit_time": exit_t})
    return {"operations": _build_ops_safe(assignments)}


def algorithm(prob_info, timelimit=60):
    """OGC2026 entry point -- signature fixed by the contest harness."""
    import importlib
    import time as _time
    _t0 = _time.time()
    _assert_defaults()  # [SUB8] submission-path self check (print-only)

    # SINGLE ENGINE, NO ROUTING (md D0/D9): instead of predicting which
    # raster mode / beam width fits this instance via thresholds, all four
    # workers below run in parallel on every instance and the best FINAL
    # objective wins -- adaptation by observation, not classification.
    #   W1: conservative raster, proven generalist config, auto beam width
    #   W2: conservative raster, SMALL width (0.35x) -- small-instance peak
    #   W3: TIGHT raster (no ghost gaps + exact verify), congested winner
    #   W4: TIGHT raster, mid width (0.6x), skyline-mix scoring
    # The B ladder is the diversification axis (deterministic -- random
    # noise is deliberately avoided to keep runs reproducible).
    os.environ["OGC_S"] = "2"
    # [CPP v20] C++ core default-ON; beamsolver guards import + every call
    # site, so a load/call failure lands on the numba path unchanged.
    os.environ.setdefault("OGC_CPP", "1")
    os.environ.setdefault("OGC_CPPBP", "1")
    os.environ["OGC_NATIVE"] = "1"  # fused numba sweep (numba is in the
    #                                 official ogc2026 environment)
    os.environ["OGC_TIGHT"] = "0"   # parent process: conservative (safe
    #                                 superset masks for the post-passes)
    # [SUB1] guarded solver import: beamsolver -> native_kernel -> numba.
    # If the native chain fails on the judge host, retry with the FFT
    # (non-native) path -- it exists but was unreachable behind an
    # unprotected import; if even that fails, return the dependency-free
    # safety-net solution instead of raising out of algorithm().
    try:
        import gridsolver
        import beamsolver
        importlib.reload(gridsolver)
        importlib.reload(beamsolver)
    except Exception:
        os.environ["OGC_NATIVE"] = "0"
        try:
            import gridsolver
            import beamsolver
            importlib.reload(gridsolver)
            importlib.reload(beamsolver)
        except Exception:
            return _fallback_solution(prob_info)

    WORKERS = (
        # (order, rank, pos_div, beam_mult, schedule, pos_lam, tight, beta,
        #  esh)
        # Diversification axes: ORDER x raster (the order axis measured
        # largest: lst -50% on prob_21, edd_at -21% on prob_15) plus the
        # future-value beta and the in-worker width ladder.  The E2 layer-
        # accounting flag (esh) has an instance-dependent sign (-19/-11/-9%
        # on 28/21/30, +6/+3.5% on 13/26), and flipping a worker slot to it
        # measured zero-sum (won 30 -14%, lost 21 +12.5% -- every slot is
        # load-bearing), so esh runs as ladder rung 3 on LEFTOVER worker
        # time instead of occupying a slot (see parallel_multi).
        # [F1] REVERTED: w1 rung 1 as "dispatch@lst" (time-major order,
        # lens rungs keeping lst) looked Pareto on an 11-case A/B (11@60
        # 35,434 -> 30,709, 5-version plateau broken; 10 cases identical)
        # -- but the case list omitted prob_21, and the full 40-problem
        # bench showed why that seat is load-bearing: 21 +32.2%
        # (580,901 -> 767,884; w1's rung-1 lst IS the measured "lst -50%
        # on prob_21" line), 6 +19.7%, 7 +4.7%, 34 +3.1% vs wins 11
        # -13.3%, 29 -5.2%, 22 -4.4%, 3 -0.6% -- 29/40 all-time vs
        # v11.1's 36/40.  The dispatch order stays available via
        # OGC_DISPS=1 (reproduces the prob_11 lead) / OGC_DISPW /
        # OGC_DISP; no default seat exists without displacing a winner.
        ("edd_big", "v0",  False, 1.0, "flat", 0.01, "0", 1.5, "0"),
        ("lst",     "v0",  False, 1.0, "flat", 0.01, "0", 1.5, "0"),
        ("edd_at",  "gh",  False, 1.0, "flat", 0.5,  "1", 0.5, "0"),
        ("lst",     "v0",  False, 0.6, "flat", 0.5,  "1", 1.5, "0"),
    )
    if os.environ.get("OGC_NOESH") == "1":  # A/B scaffolding (local only)
        WORKERS = tuple(cfg[:8] + ("0",) for cfg in WORKERS)
    _dw = os.environ.get("OGC_DISPW")  # [F1] A/B scaffolding (local only):
    if _dw is not None and _dw.isdigit():  # swap worker N's order axis to
        WORKERS = tuple(("dispatch",) + cfg[1:]  # the time-major dispatch
                        if j == int(_dw) else cfg  # order
                        for j, cfg in enumerate(WORKERS))
    _ds = os.environ.get("OGC_DISPS")  # [F1] surgical: worker N's RUNG 1
    if _ds is not None and _ds.isdigit():  # only (lens rungs keep their
        WORKERS = tuple(("dispatch@" + cfg[0],) + cfg[1:]  # own order)
                        if j == int(_ds) else cfg
                        for j, cfg in enumerate(WORKERS))
    cfgs = beamsolver.PORTFOLIO  # sequential rescue path only

    # safety net: an always-feasible O(n) solution held in reserve; the main
    # pipeline's own results are validated before being returned, so a slow
    # judge machine, an unexpected exception, or a validation failure can
    # never produce "infeasible" -- worst case we score with the fallback.
    safe_sol = _fallback_solution(prob_info)
    try:
        from utils import check_feasibility
        # 4-core parallel worker matrix on EVERY instance and timelimit.
        # The only exception is an infrastructure guard, not a problem
        # classification: below ~25s the process-spawn + JIT fixed cost
        # would eat the whole budget, so run sequentially.
        if timelimit < 25.0:
            sol, _stats = beamsolver.solve_multi(prob_info,
                                                 timelimit=timelimit * 0.92,
                                                 configs=cfgs,
                                                 verbose=False)
            if _time.time() - _t0 < timelimit * 0.99:
                res = check_feasibility(prob_info, sol)
                if not res["feasible"]:
                    return safe_sol
            return sol

        env = {"OGC_S": os.environ["OGC_S"],
               "OGC_NATIVE": os.environ["OGC_NATIVE"]}
        from parallel_multi import solve_parallel, spawn_works
        # canary: prove the host can actually spawn workers BEFORE betting
        # the budget on the parallel path -- if not, run sequentially with
        # the FULL remaining budget instead of a leftover rescue slice
        if not spawn_works():
            remaining = timelimit * 0.92 - (_time.time() - _t0)
            sol, _stats = beamsolver.solve_multi(prob_info,
                                                 timelimit=remaining,
                                                 configs=cfgs,
                                                 verbose=False)
            if _time.time() - _t0 < timelimit * 0.99:
                res = check_feasibility(prob_info, sol)
                if not res["feasible"]:
                    return safe_sol
            return sol
        obj, sol, amaps = solve_parallel(prob_info, timelimit, WORKERS, env)
        _t_construct = _time.time() - _t0  # OBS 2: budget waterfall
        # T2 (D6xD7): blocks the four lenses DISAGREE on (>=2 distinct bay
        # assignments) are exactly the hard decisions -- the losers' maps
        # are the only reusable output of 3/4 of the compute
        disagree = []
        if len(amaps) >= 2:
            keys = set().union(*amaps)
            disagree = [k for k in keys
                        if len({m.get(k) for m in amaps
                                if k in m}) >= 2]
        if sol is None:
            # parallel path failed entirely -> sequential portfolio fallback
            remaining = timelimit * 0.92 - (_time.time() - _t0)
            if remaining < 5.0:
                return safe_sol
            sol, _stats = beamsolver.solve_multi(prob_info,
                                                 timelimit=remaining,
                                                 configs=cfgs,
                                                 verbose=False)
        else:
            # T4 (rung_G): guided reconstruction -- defined below, fired
            # ONCE when the improvement loop stalls (doc: "after one loop
            # revolution, if time remains"), so it spends only time the
            # proven post-passes can no longer convert.  The incumbent's
            # entry-ascending order makes it reconstructible as ONE beam
            # path (every vacated-slot predecessor comes first); a beam
            # over that order with a SOFT bay anchor searches the
            # incumbent's neighbourhood at reconstruction scale -- the
            # neighbourhood K~20 LNS provably cannot reach (0 accepts in
            # 3 independent expansions).  min() keeps it harmless; T1
            # incumbent pruning cuts dominated subtrees for free.
            def _rung_g(cur_obj, cur_sol, budget_s):
                ent, ext = {}, {}
                for _t2, _ops in cur_sol["operations"].items():
                    for o in _ops:
                        if o["type"] == "ENTRY":
                            ent[o["block_id"]] = (int(_t2), o["bay_id"])
                        elif o["type"] == "EXIT":
                            ext[o["block_id"]] = int(_t2)
                nb = len(prob_info["blocks"])
                if len(ent) != nb:
                    return cur_obj, cur_sol
                order_G = sorted(ent, key=lambda b: (ent[b][0],
                                                     ext.get(b, 0), b))
                anchor = {b: ent[b][1] for b in ent}
                area_g = float(sum(b["width"] * b["height"]
                                   for b in prob_info["bays"]))
                b_g = max(beamsolver.B_MIN,
                          beamsolver.auto_beam_width(nb, area_g,
                                                     budget_s) // 2)
                sol_g, _sg = beamsolver.solve_beam(
                    prob_info, timelimit=budget_s, beam_init=b_g,
                    order_name="edd_big", rank_mode="v0", schedule="flat",
                    pos_lam=0.01, incumbent=cur_obj, fut_beta=0.0,
                    order_ids=order_G, anchor=anchor, verbose=False)
                sol_gr = beamsolver.rebalance(prob_info, sol_g)
                for cand in (sol_gr, sol_g):
                    res_g = check_feasibility(prob_info, cand)
                    if (res_g["feasible"]
                            and res_g["objective"] < cur_obj - 1e-6):
                        cur_obj, cur_sol = res_g["objective"], cand
                if os.environ.get("OGC_T4LOG") == "1":
                    print(f"  [rung_G] B={b_g} budget={budget_s:.0f}s"
                          f" -> obj={cur_obj:.0f}", flush=True)
                return cur_obj, cur_sol

            # improvement loop on the winner: alternate the monotone
            # post-passes until the deadline or until neither improves --
            # long limits previously left 30%+ of the budget unused
            # T5-ext: the improvement window runs a deterministic PASS
            # LADDER -- fixed slice sizes, fixed operator order, and
            # iteration-cooled LNS -- so what happens no longer depends on
            # wall-clock jitter (measured: the old min(remaining, 45)
            # partial slices made prob_16@240 oscillate 34106<->42766
            # between runs).  Time decides only HOW FAR down the ladder
            # the run gets (monotone, like the worker rung ladder).
            # Order is evidence-based: LNS starts at k=14 (the measured
            # winner on z2-slack instances; k=8 never won in any log),
            # rung_G takes one fixed slot, k=20 LNS cycles fill leftovers.
            _lg = os.environ.get("OGC_LOOPLOG") == "1"
            _dis = disagree if os.environ.get("OGC_T2") == "1" else None

            def _rem():
                return timelimit * 0.96 - (_time.time() - _t0) - 2.0

            _dbg = os.environ.get("OGC_DEBUG") == "1"

            def _adopt(cand, label, t_start=None):
                res_c = check_feasibility(prob_info, cand)
                good = (res_c["feasible"]
                        and res_c["objective"] < obj - 1e-6)
                if _dbg and t_start is not None:  # OBS 2: PASS line
                    print(f"PASS name={label}"
                          f" t={_time.time() - t_start:.1f}"
                          f" gain={(obj - res_c['objective']) if good else 0:.0f}",
                          flush=True)
                if good:
                    if _lg:
                        print(f"  [pass] {label} {obj:.0f} -> "
                              f"{res_c['objective']:.0f}", flush=True)
                    return res_c["objective"], cand
                return None

            # [C3] FBI (forward-backward justification): deterministic,
            # objective-monotone (right pass invariant, left pass can only
            # REDUCE Z1 by pulling late blocks into space the right pass
            # opened), seconds-cheap via the [C1] pairwise time-invariant
            # collision matrix.  Confirmation run: prob_40 -4,669 direct;
            # C2 (compression as LNS prep) measured null/negative
            # (rho mid-band flat, prob_16 LNS gain 191 -> 0) -- REJECTED,
            # so justify enters only as a direct improver under _adopt's
            # strictly-improving gate.
            LADDER = [("justify", 2.0, 0), ("repair", 25.0, 0),
                      ("lns", 45.0, 14), ("rebalance", 4.0, 0),
                      ("rung_g", 44.0, 0), ("lns", 45.0, 20),
                      ("rebalance", 4.0, 0)]
            EXTRA = [("justify", 2.0, 0), ("lns", 45.0, 20),
                     ("rebalance", 4.0, 0)]
            _jcache: dict = {}  # [C-A A2] persistent justify flag cache
            step_i = 0
            while True:
                in_extra = step_i >= len(LADDER)
                if in_extra:
                    kind, need, kk = EXTRA[(step_i - len(LADDER))
                                           % len(EXTRA)]
                else:
                    kind, need, kk = LADDER[step_i]
                step_i += 1
                rem_now = _rem()
                if rem_now < 4.0:
                    break
                _tp = _time.time()
                if kind == "repair":
                    # cheap and monotone: adaptive slice is safe here
                    got = _adopt(beamsolver.time_repair(
                        prob_info, sol,
                        timelimit=min(rem_now, need)), "repair", _tp)
                elif kind == "rebalance":
                    got = _adopt(beamsolver.rebalance(prob_info, sol),
                                 "rebalance", _tp)
                elif kind == "justify":  # [C3] FBI, kill switch for A/B
                    if (os.environ.get("OGC_NOC3") == "1"
                            or rem_now < 3.0):
                        continue
                    sol_j, _mv = beamsolver.justify_time(
                        prob_info, sol, direction="fbi", flag_cache=_jcache)
                    got = _adopt(sol_j, "justify", _tp)
                elif kind == "lns":
                    if rem_now < need + 4.0:
                        if not in_extra:
                            continue  # fixed slice must fit (no partials)
                        # nothing larger will ever fit again -- run ONE
                        # closer pass before stopping.  At SHORT windows
                        # (60s: ~15s leftover) no fixed slice fits and
                        # v7's partial-LNS wins were lost (measured @60:
                        # prob_29 +8.4%, 16 +5.4%, 11 +4.5%).  The slice
                        # adapts but the ITERATION budget is fixed, so the
                        # trajectory is deterministic whenever the
                        # iterations complete inside the slice; the wall
                        # cap stays as pure safety.
                        if rem_now >= 10.0:
                            # k=8 here: short windows fit more iterations
                            # of SMALL ruins (v7's @60 wins all came from
                            # its k=8 first-round LNS; k=14 emerged only
                            # in round 2+, which @60 never reached)
                            got = _adopt(beamsolver.time_repair(
                                prob_info, sol, timelimit=rem_now - 4.0,
                                mode="lns", lns_k=8, max_iters=120,
                                disagree=_dis), "lns_final", _tp)
                            if got is not None:
                                obj, sol = got
                            got = _adopt(beamsolver.rebalance(
                                prob_info, sol), "rebalance")
                            if got is not None:
                                obj, sol = got
                        break
                    got = _adopt(beamsolver.time_repair(
                        prob_info, sol, timelimit=need, mode="lns",
                        lns_k=kk, max_iters=120, disagree=_dis),
                        f"lns_k{kk}", _tp)
                else:  # rung_g -- one fixed slot
                    if (rem_now < need + 4.0
                            or os.environ.get("OGC_NOT4") == "1"):
                        continue
                    try:
                        new_obj, new_sol = _rung_g(obj, sol, need - 4.0)
                        got = ((new_obj, new_sol)
                               if new_obj < obj - 1e-6 else None)
                    except Exception:
                        got = None
                if got is not None:
                    obj, sol = got

        if os.environ.get("OGC_DEBUG") == "1":  # OBS 2+5
            try:
                _now = _time.time() - _t0
                print(f"BUDGET construct={_t_construct:.1f}"
                      f" improve={_now - _t_construct:.1f}"
                      f" tail_unused={timelimit - _now:.1f}"
                      f" (of {timelimit:.0f})", flush=True)
                _e2, _x2 = {}, {}
                for _t3, _ops3 in sol["operations"].items():
                    for o3 in _ops3:
                        if o3["type"] == "ENTRY":
                            _e2[o3["block_id"]] = int(_t3)
                        elif o3["type"] == "EXIT":
                            _x2[o3["block_id"]] = int(_t3)

                def _parea(bd):
                    vs = bd["shape"][0]["layers"][0]
                    s = 0.0
                    for i2 in range(len(vs)):
                        xa, ya = vs[i2]
                        xb, yb = vs[(i2 + 1) % len(vs)]
                        s += xa * yb - xb * ya
                    return abs(s) / 2.0

                _blks = prob_info["blocks"]
                _A = float(sum(b["width"] * b["height"]
                               for b in prob_info["bays"]))
                _evs = []
                for _bi in _e2:
                    _a = _parea(_blks[_bi])
                    _evs.append((_e2[_bi], _a))
                    _evs.append((_x2[_bi], -_a))
                _evs.sort()
                _occ = _integ = _peak = 0.0
                _prev = _evs[0][0]
                for _tt, _da in _evs:
                    _integ += _occ * (_tt - _prev)
                    _prev = _tt
                    _occ += _da
                    _peak = max(_peak, _occ)
                _mk = max(1, _evs[-1][0] - _evs[0][0])
                _wt = [_e2[b] - _blks[b]["release_time"] for b in _e2]
                print(f"PACK rho_sus={_integ / (_A * _mk):.3f}"
                      f" rho_peak={_peak / _A:.3f}"
                      f" wait_avg={sum(_wt) / max(1, len(_wt)):.1f}",
                      flush=True)
            except Exception:
                pass

        if _time.time() - _t0 < timelimit * 0.995:
            res = check_feasibility(prob_info, sol)
            if not res["feasible"]:
                return safe_sol
        return sol
    except Exception:
        return safe_sol


if __name__ == "__main__":
    import argparse
    import json
    import time

    from utils import check_feasibility

    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--timelimit", type=float, default=60.0)
    args = ap.parse_args()

    with open(args.instance, encoding="utf-8") as f:
        prob = json.load(f)
    t0 = time.time()
    sol = algorithm(prob, timelimit=args.timelimit)
    res = check_feasibility(prob, sol)
    print(f"instance : {prob.get('name', '?')}")
    print(f"elapsed  : {time.time() - t0:.1f}s / limit {args.timelimit}")
    print(f"feasible : {res['feasible']} (stage={res['stage']})")
    if res["feasible"]:
        print(f"objective: {res['objective']:.0f}  "
              f"(z1={res['obj1']}, z2={res['obj2']}, z3={res['obj3']})")
    else:
        for v in res["violations"][:5]:
            print("  VIOL:", v)


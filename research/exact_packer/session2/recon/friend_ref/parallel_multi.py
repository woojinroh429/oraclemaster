# -*- coding: utf-8 -*-
"""4-core parallel portfolio for OGC2026 (the evaluation server allows
400% CPU; the organizers recommend 4 worker processes).

Robustness rules (a hung or crashed worker must never cost the score):
  * results are collected via as_completed under a GLOBAL deadline --
    one hung worker cannot consume the whole collection window;
  * every worker catches its own exceptions and reports (inf, None);
  * numba's JIT cache goes to a worker-local temp dir (the project may
    live on a synced drive where concurrent cache writes can deadlock);
  * the caller keeps a sequential rescue window if ALL workers fail.
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))

# [KC/WR] ADOPTED width policy (v17, default ON): correct the LATE rungs'
# (index >= 1) width for K_COST's measured 2.6-6.4x over-prediction, by
# scaling the nominal fed to auto_beam_width (width is linear in timelimit,
# so nominal*m == K_COST/m).  Rung 0 stays legacy -- widening it is
# non-monotone (prob_38 B17->48 worsened), while the late lens rungs are
# starved by PHI x the stale K_COST (B 9-18) and pay off when fed
# (prob_30 W4r5 B11->27: that rung alone -27%).  Nominal-based recompute,
# NOT a multiplier on the miscalibrated width (a x3 multiplier blew rung 1
# B37->111 and starved everything after it).
# Validated 2026-07-17: @500 4 wins 1 same 0 regressions (30 -8.83%,
# 26 -3.50%, 40 -2.36%, 38 -0.70%, 27 same), @240 harmless, @60 full
# 40-problem bench sum -1.15% (the 3 @60-only regressions all reversed at
# server budgets), watchdogs 21/16/23 pass, no deadline forfeits.
# OGC_KCLATE=1.0 reverts to the legacy widths for A/B.
_KCLATE = float(os.environ.get("OGC_KCLATE", "3.0"))


def _worker(args):
    """Run ONE portfolio config in a fresh process; never raises.
    cfg = (order, rank_mode, pos_diverse, beam_mult, schedule, pos_lam,
           tight) -- `tight` is decided PER WORKER, not by a router: the
    conservative and TIGHT rasters compete and the best result wins."""
    prob_info, cfg, budget, env = args[:4]
    widx = args[4] if len(args) > 4 else -1  # OBS: worker id for RUNG logs
    try:
        # one thread per worker: the evaluation server caps total CPU at
        # 400%; 4 workers x default BLAS/OpenMP thread pools oversubscribe
        # it and lose throughput to context switching (an earlier submission
        # showed P4-P6 regressing 4-10% vs sequential for this reason)
        for tv in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                   "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                   "NUMBA_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
            os.environ[tv] = "1"
        for k, v in env.items():
            os.environ[k] = v
        fut_beta = 0.0
        esh = "0"
        if len(cfg) >= 9:
            esh = cfg[8]  # E2 layer accounting -- a worker axis like TIGHT
        if len(cfg) >= 8:
            fut_beta = float(cfg[7])
        _tight_s = "0"
        if len(cfg) >= 7:
            os.environ["OGC_TIGHT"] = cfg[6]
            _tight_s = cfg[6]
        os.environ["OGC_ESH"] = esh
        cfg = cfg[:6]
        # worker-local numba cache: avoids concurrent-write contention on
        # synced/network drives (4 processes JIT-compiling simultaneously)
        import tempfile
        os.environ["NUMBA_CACHE_DIR"] = tempfile.mkdtemp(prefix="ogc_nb_")
        if _HERE not in sys.path:
            sys.path.insert(0, _HERE)
        import beamsolver
        from utils import check_feasibility

        # [TIGHT-REV] the env write above only works under spawn (Windows).
        # Under fork -- which is what Linux and therefore the judge server
        # use -- the child inherits the parent's already-imported modules and
        # that import is a no-op, so W3/W4 silently ran the conservative
        # raster.  Set the live module attributes instead, the way every
        # other worker axis is set.  orient_geo's memo key includes TIGHT so
        # masks regenerate; solve_beam re-registers geometry every call.
        if os.environ.get("OGC_TIGHTREV", "1") == "1":
            import gridsolver as _gs_tr
            _tight_on = (_tight_s == "1")
            _gs_tr.TIGHT = _tight_on
            beamsolver.TIGHT = _tight_on
            if os.environ.get("OGC_DEBUG") == "1":
                print("TIGHTREV w=%d TIGHT=%s" % (widx, _tight_on),
                      flush=True)

        on, rm, pd, bm, sched, lam = cfg
        # [F1] surgical order split "r1@ladder": rung 1 runs the order
        # left of the @, the lens rungs 3-6 keep the order right of it.
        # Measured need: a full worker-order swap (w1 lst->dispatch) won
        # prob_11 -13.3% via rung 1 but lost 30@500 +11.1% and 13 +3.5%
        # via the INHERITED lens rungs -- the win and the losses live on
        # different rungs, so the axes must be separable.
        r1_on = on
        if "@" in on:
            r1_on, on = on.split("@", 1)
        n_blocks = len(prob_info["blocks"])
        area = float(sum(b["width"] * b["height"]
                         for b in prob_info["bays"]))
        # [TRI] overload-regime switch (v18, DEFAULT ON; OGC_TRISW=0 for
        # A/B).  Triage order pays ONLY in an overloaded rush (reference-
        # solution reverse engineering: defer the big blocks -- tardiness
        # costs per BLOCK, space costs area x time).  Regime detector =
        # demand ratio sum(bbox_area x proc) / (total bay area x due_max):
        # measured wins at 0.93-1.04 (line-level 27 -13.8% / 38 -11.0% /
        # 40 -13.6%), losses at <= 0.79, border 0.84 (-2.4%, foregone).
        # THR 0.9 = the safe side.  Instance-derived deterministic rule --
        # not name routing.  When it fires, every worker's base order
        # becomes edd_tri (rung 2's pure-conservative edd_big stays as a
        # non-tri insurance line under min()) and the beam gets
        # n_entry_opts=2 ("wait one exit for a tighter fit" candidates).
        # When it does not fire the whole run is byte-identical
        # (verified: prob_21@60 = 580,901 exact).
        _tri = os.environ.get("OGC_TRISW", "1") == "1"
        _hz_ratio = 0.0  # [HZ v19.8] demand ratio for the band gate
        if _tri:
            try:
                _bl = prob_info["blocks"]
                _dm = max(b["due_date"] for b in _bl)
                _dem = 0.0
                for _b in _bl:
                    _vs = _b["shape"][0]["layers"][0]
                    _xs = [v[0] for v in _vs]
                    _ys = [v[1] for v in _vs]
                    _dem += ((max(_xs) - min(_xs)) * (max(_ys) - min(_ys))
                             * _b["processing_time"])
                _hz_ratio = _dem / max(1e-9, area * _dm)
                _tri = (_hz_ratio
                        >= float(os.environ.get("OGC_TRITHR", "0.84")))
                # [TR-B v19.9] threshold 0.9 -> 0.84: the uncovered
                # [0.84, 0.90) zone (our ONLY remaining deficit vs the
                # reference team, prob_33 +1.9%) wins with the plain TRI
                # bundle at default constants -- 33@500 7,481,427 ->
                # 7,215,746 (-3.55%, all-time).  0.79 extension measured
                # +11~30% on 39 -> lower bound stays 0.84.  [PX2-D]'s old
                # "+3.0% at 0.84" verdict inverted on the v19.9 terrain.
            except Exception:
                _tri = False
        # [HZ v19.8] band gate: rank += 0.5*h_Z1 only when the demand
        # ratio sits in [0.95, 1.02) -- capacity binding but not hopeless.
        # Measured @500: in-band 38 -3.03% (34,206,419 all-time, beats the
        # reference team by -4.3%); out-of-band applications mislead
        # (27 [1.041] +2.15%, 40 [0.933] +2.99%).  OGC_HZBAND=0 reverts.
        if os.environ.get("OGC_TRB", "1") == "1" and _tri:
            # [TR v19.9] ratio-banded triage constants (detector 4th use).
            # The fired trio's optima sort by demand ratio -- measured
            # sharp peaks (@500, base v19.8):
            #   ratio >= 1.02 (superoverload, 27-type): TRIMULT 1.5
            #     -> 27 = 23,426,240 (-2.27%, all-time; 1.35 collapses)
            #   [0.95, 1.02) (critical, 38-type): keep 2.0/0.2 (+HZ band)
            #   [0.90, 0.95) (40-type): TRIREL 0.1
            #     -> 40 = 1,759,505 (-2.98%, all-time; 0.05/0.15 flat)
            # OGC_TRB=0 reverts to the flat 2.0/0.2 constants.
            if _hz_ratio >= float(os.environ.get("OGC_TRB_HI", "1.02")):
                os.environ["OGC_TRIMULT"] = \
                    os.environ.get("OGC_TRB_M", "1.5")
            elif 0.90 <= _hz_ratio < float(os.environ.get("OGC_TRB_LO",
                                                          "0.95")):
                # [TR-B] R0.1 stays a [0.90, 0.95) band: the new
                # [0.84, 0.90) zone measured best with DEFAULT constants
                # (33: R0.1 arm +3.6% vs default -3.55%).
                os.environ["OGC_TRIREL"] = \
                    os.environ.get("OGC_TRB_R", "0.1")
        if os.environ.get("OGC_HZBAND", "1") == "1":
            _hlo = float(os.environ.get("OGC_HZLO", "0.95"))
            _hhi = float(os.environ.get("OGC_HZHI", "1.02"))
            if _hlo <= _hz_ratio < _hhi:
                beamsolver._HZ = True
                beamsolver._HZW = float(os.environ.get("OGC_HZW", "0.5"))
        # [BX v19.3] B_MAX TRI-gate: lift the v1-era arbitrary width
        # ceiling (96) to 192 for NON-overloaded instances only.  Fired
        # instances keep 96 byte-identically (their width path is the
        # KCLATE 4.0 re-earn).  Same instance-derived detector as TRI/KCG
        # -- third use, zero new thresholds.  OGC_BMAXG=0 reverts.
        if os.environ.get("OGC_BMAXG", "1") == "1" and not _tri:
            beamsolver.B_MAX = int(os.environ.get("OGC_BMAXG_V", "192"))
        _ne = 1
        if _tri:
            # [TRI2] v18.1 seat split under min() -- measured @500 on the
            # fired trio (vs all-tri v18):
            #   W1 -> edd_tri   (blanket triage)
            #   W2 -> keeps lst (insurance for unseen fired instances
            #                    where the legacy order might still win)
            #   W3 -> edd_tri2  (selective: early-released bigs stay
            #                    anchors -- won 38: 36.15M vs 37.04M)
            #   W4 -> edd_tri   (TIGHT/v0/bm.6 x tri combo -- won 27
            #                    23.97M (-4.9%) and 40 1,940,154 (-3.7%))
            # min() picks per instance; rung 2 (edd_big) stays a non-tri
            # insurance line in every worker.
            if widx != 1:
                _to = "edd_tri2" if widx == 2 else "edd_tri"
                on = _to
                r1_on = _to
            _ne = 2

        # Budget-first B ladder: rung 1 gets the WHOLE remaining budget
        # (large instances consume it and stop there -- no efficiency
        # loss).  Rung 2 fires only when rung 1 leaves >=10s, i.e. on
        # small/mid instances -- and is NOT a half-width rerun of the same
        # config (measured near-duplicate: prob_16 rung2 61,481 vs rung1
        # 58,169) but the pure conservative line (edd_big, v0, lam .01,
        # beta 0): the beta=1.5 worker matrix no longer covers it, and on
        # low-congestion instances beta only disturbs placement chains
        # (prob_16: 42,766 with beta 0 vs 55,900 with beta 1.5).  min()
        # over rungs keeps it harmless where rung 1 dominates.
        t0 = time.time()
        best_obj, best_sol = float("inf"), None
        # per-rung lens flags: (esh = E2 shadow union, ect = E3 layered
        # contact, eal = P-A aligned-contact alpha, 0 = off).  The lenses
        # are exclusive lines, not combinations (measured: esh1+ect1 ==
        # ect1 on 21/28/30).
        # v11: the v10 gh-rung2 -> EAL swap is REVERTED (measured zero-sum
        # at 60s: won 13 -4.7% but lost 23 +14.4% -- the swapped-out TIGHT
        # pure copy was 23's winner; the EAL 0.25 lens already exists at
        # rung 6).  A v5-w3 restoration attempt at the OTHER TIGHT
        # worker's rung 2 also measured zero-sum (27 +5.7%: rung-2 copies
        # share content but not incumbents, so each is a distinct line)
        # and could not reproduce prob_20 anyway (rung-2 nominal = 62% of
        # the width the line needs) -- reverted too; prob_20-class
        # recovery is registered as an open width-economics problem.
        rung2 = ("edd_big", "v0", False, "flat", 0.01, 0.0, 1.0,
                 False, False, 0.0)
        rungs = [(r1_on, rm, pd, sched, lam, fut_beta, bm, esh == "1",
                  False, 0.0), rung2]
        # [RV3] v18.2: on TRI-fired instances, tri-family workers skip the
        # pure-conservative rung 2 -- measured: on fired larges only ~2
        # rungs fire, and the tri x esh interaction is the winner channel
        # (27's winner = W4-tri x esh; 40 = 1,931,503 all-time best when
        # esh gets rung-2's budget).  W2 (widx 1) keeps lst-r1 + edd_big-r2
        # double insurance, so the non-tri safety net survives.  Fired
        # instances' rung-2 line lost EVERYWHERE locally (27: 28.2M /
        # 38: 44-48M / 40: 2.4-2.56M vs winners 25.2/36.2/1.93M).
        # OGC_TRIR2=0 disables for A/B.  Non-fired: byte-identical.
        if _tri and widx != 1 \
                and os.environ.get("OGC_TRIR2", "1") == "1":
            rungs = rungs[:1]
        # [M] merged-lens beam: rung 1 hosts base/a25/a50 as strata of ONE
        # beam (lenses participate from block 1, no firing lottery), the
        # lens rungs 3-6 are replaced by it; the pure-conservative rung 2
        # stays (different order/beta -- not a mergeable axis).
        m_on = os.environ.get("OGC_MERGE") == "1"
        if not m_on and os.environ.get("OGC_NOESH") != "1":
            # rungs 3-4 (layer accounting): the worker's own config with
            # E2 shadow scoring, then E3 layered contact, run on time the
            # 2-rung ladder would otherwise leave unused.  Additive under
            # min() -- no existing line is sacrificed (a worker-slot flip
            # measured zero-sum: won prob_30 -14% but lost prob_21 +12.5%).
            # E2 first: it costs nothing per node, so it makes the most of
            # SHORT leftovers (prob_30@60s: esh-first 2.36M vs ect-first
            # 2.72M); E3's per-node cost (+30-80%) pays off when a longer
            # budget leaves rung 4 real time (21/30 -19% isolated).
            rungs.append((on, rm, pd, sched, lam, fut_beta, bm,
                          True, False, 0.0))
            rungs.append((on, rm, pd, sched, lam, fut_beta, bm,
                          False, True, 0.0))
            # rungs 5-6 ([P] step 4): the P-A aligned-contact lens, both
            # alpha lines -- fires only on mid-size leftovers (isolated:
            # prob_30 -21% at alpha .5, prob_38 -3.6% at alpha .25; the
            # winning alpha is instance-dependent, so both run and min()
            # decides)
            rungs.append((on, rm, pd, sched, lam, fut_beta, bm,
                          False, False, 0.5))
            rungs.append((on, rm, pd, sched, lam, fut_beta, bm,
                          False, False, 0.25))
        # [F1] dispatch rung (OPT-IN, default off): the worker's own line
        # with the TIME-MAJOR dispatch order appended as a last rung.
        # Isolated, the line is real (prob_40 outright winner -3.3%, T
        # 3393 vs 3524/3602, rho_sus .375 vs .360/.369) -- but as a LAST
        # rung it starves: at 500s the margin clamp leaves it rem~35s ->
        # B=2 on its own target class (38/40), and the full-pipe A/B
        # measured 9/9 cases identical.  Same root as the prob_20
        # width-economics problem (the seat, not the line, decides the
        # width).  Kept for future width-economics experiments; the
        # ADOPTED entry is w1's rung-1 order split (see myalgorithm).
        if os.environ.get("OGC_DISP") == "1":
            rungs.append(("dispatch", rm, pd, sched, lam, fut_beta, bm,
                          False, False, 0.0))
        # [L3] P-B dead-space lens rung (OPT-IN): the worker's own line with
        # contact = contact - created-pocket-count (knob-free, cells).  The
        # sweep_pk kernel exists; this appends it as an ADDED last rung (min
        # below, harmless) to A/B whether pure dead-space beats esh/ect/eal
        # in a wide seat.  11th tuple element = per-rung E_PK flag.
        if os.environ.get("OGC_PKRUNG") == "1":
            rungs.append((on, rm, pd, sched, lam, fut_beta, bm,
                          False, False, 0.0, True))
        # T5 (D8): rung widths are precomputed from NOMINAL budget shares,
        # not from the measured leftover seconds.  The old form coupled a
        # search parameter (width) to wall-clock, so any engine speed-up
        # (or a slower judge machine) silently ran a DIFFERENT algorithm
        # configuration (measured: [S] made prob_28@60s +9.1% through this
        # channel alone).  Widths now depend only on (instance, budget);
        # timing decides ONLY how many rungs fire -- under min() over
        # rungs, more speed can then only add lines, never distort them.
        # PHI is a calibration TABLE reproducing the OLD ladder's typical
        # leftover fractions, which are budget-dependent (rung-1 fixed
        # costs don't amortise at short budgets): observed 0.83/0.69/0.56
        # at 240s but only ~0.62/0.38/0.22 at 60s.  A single compromise
        # vector made the 60s rung 2 over-wide and starved rungs 3-4 (the
        # E-lines) -- measured @60: prob_22 +2.6%, 29 +8.4%, 27 +3.6%.
        # Budget-dependence is legal under T5: the ban is on wall-clock /
        # engine-speed inputs, and auto_beam_width is already a function
        # of the budget.
        # [P] step 0: the long-budget branch is RESTORED to the measured
        # v7 fractions (0.83/0.69/0.56 at 240s) instead of the earlier
        # compromise (0.7/0.5/0.35) -- the compromise made rungs 2-4
        # narrower than what every long-budget result was validated on,
        # and is a suspect in the server-P4 +27% regression.  The margin
        # clamp below keeps the wider nominals safe on oversized
        # instances.
        PHI = ((1.0, 0.83, 0.69, 0.56, 0.44, 0.34) if budget >= 100.0
               else (1.0, 0.62, 0.38, 0.22, 0.14, 0.10))
        t5_off = os.environ.get("OGC_NOT5") == "1"  # A/B scaffolding
        # [F4] elite transplant chain (OGC_ELIT gate): a rung's quartile-
        # depth top-m snapshots ride into the NEXT same-order rung as
        # extra-slot immigrants -- zero width loss, hybrid lineage open.
        # Only order-sharing rungs qualify (rung 2's edd_big and a split
        # rung-1 order place different block sets -> states not legal).
        elit_on = os.environ.get("OGC_ELIT") == "1"
        elite = None
        for rung, _rt in enumerate(rungs):
            (r_on, r_rm, r_pd, r_sc, r_lam, r_fb, r_bm, r_esh,
             r_ect, r_eal) = _rt[:10]
            r_epk = _rt[10] if len(_rt) > 10 else False  # [L3] P-B lens
            rem = budget - (time.time() - t0)
            # J4 (jitter): the firing gate drops from 10s to the MEASURED
            # per-rung fixed cost (JIT ~2s hits rung 1 only; setup <1s) --
            # the old 10s was a hidden prediction ("a 10s rung is
            # worthless"), and its binary boundary turned timing noise
            # into a one-way lottery (prob_23@60: same config oscillated
            # 2.12M<->2.43M, +-14%).  A truncated rung still returns a
            # complete solution (anytime guard) and min() filters it; the
            # FLOOR is a single problem-invariant constant by rule --
            # value judgement moves from the gate (prediction) to min()
            # (observation).
            if rem < 3.0:
                break
            beamsolver.E_SH = r_esh
            beamsolver.E_CT = r_ect
            beamsolver.E_AL = r_eal > 0.0
            beamsolver.E_PK = r_epk  # [L3] per-rung P-B dead-space lens
            if r_eal > 0.0:
                beamsolver.EAL_ALPHA = r_eal
            if t5_off:  # pre-T5: width from measured leftover seconds
                b_auto = beamsolver.auto_beam_width(n_blocks, area, rem)
            else:
                # width = min(nominal, remaining): the nominal share rules
                # in the normal regime (T5 invariance), but when earlier
                # rungs overran their share -- bigger-than-calibrated
                # instances or a slower judge machine -- the clamp degrades
                # the width gracefully instead of letting one over-wide
                # rung starve the E-rungs out of firing entirely (the
                # suspected server-P4 +27% signature: losing rungs 3-4 is
                # worth ~+23% on the F4 class)
                nominal = budget * PHI[min(rung, len(PHI) - 1)]
                if rem < nominal * 0.95:  # real overrun only -- a strict
                    nominal = rem         # min() re-couples widths to the
                    #                       clock at integer boundaries
                _nom_w = nominal          # width-formula input only
                if _KCLATE != 1.0 and rung >= 1:
                    _kl = _KCLATE
                    if os.environ.get("OGC_KCT4", "1") == "1" and _tri:
                        # [KCG v19.2] instance-derived re-earn: when the
                        # TRI overload detector fires, the EXN+MEMO kernel
                        # speed-up EARNS one extra multiplier step (3->4).
                        # Measured: fired 38@500 35,275,791 (-1.48%, beats
                        # the reference solution) / 40 -2.08%; unfired
                        # probs keep the 3.0 code path byte-identical
                        # (16@240 / 23@60 exactly reproduce v19), so the
                        # non-overload server classes carry zero downside.
                        _kl = 4.0
                    _nom_w = nominal * _kl  # == corrected K_COST/m
                b_auto = beamsolver.auto_beam_width(n_blocks, area, _nom_w)
            if r_sc == "flat":
                b_auto = max(beamsolver.B_MIN, b_auto // 2)
            elif r_sc == "hybrid":
                b_auto = max(beamsolver.B_MIN, int(b_auto * 0.85))
            b = max(beamsolver.B_MIN, int(b_auto * r_bm))
            _rt0 = time.time() - t0
            _same_order = elit_on and r_on == on and "@" not in r_on
            _snap = {} if _same_order else None
            sol, _st = beamsolver.solve_beam(
                prob_info, timelimit=rem, beam_init=b, order_name=r_on,
                rank_mode=r_rm, pos_diverse=r_pd, schedule=r_sc,
                pos_lam=r_lam,
                n_entry_opts=_ne,  # [TRI] 2 in the overload regime
                incumbent=best_obj,  # D3: rung1 result prunes rung2
                fut_beta=r_fb,
                merge=(m_on and rung == 0),  # [M] strata beam at rung 1
                snap_out=_snap,             # [F4] export elites
                immigrants=elite if _same_order else None,
                verbose=False)
            if _same_order and _snap:
                elite = _snap  # [F4] feed the NEXT same-order rung
            if elit_on and os.environ.get("OGC_DEBUG") == "1":
                print(f"ELIT w={widx} r={rung}"
                      f" imm={'y' if (_same_order and rung > 0) else 'n'}"
                      f" mask={_st.get('lens_mask')}", flush=True)
            if (m_on and rung == 0
                    and os.environ.get("OGC_DEBUG") == "1"):
                print(f"STRATA w={widx} named={_st.get('lens_named')}"
                      f" best_mask={_st.get('lens_mask')}", flush=True)
            # cheap in-worker rebalance (seconds): rungs must be compared
            # AFTER the bay-flip fix, otherwise a locally-balanced but
            # globally worse rung wins the race
            sol_r = beamsolver.rebalance(prob_info, sol)
            robj = float("inf")
            for cand in (sol_r, sol):
                res = check_feasibility(prob_info, cand)
                obj = res["objective"] if res["feasible"] else float("inf")
                robj = min(robj, obj)
                if obj < best_obj:
                    best_obj, best_sol = obj, cand
            if os.environ.get("OGC_DEBUG") == "1":  # OBS 1+4
                print(f"RUNG w={widx} r={rung} t0={_rt0:.1f} B={b}"
                      f" t1={time.time() - t0:.1f} obj={robj:.0f}"
                      f" win={1 if robj <= best_obj + 1e-9 else 0}",
                      flush=True)
                print(f"BEAM w={widx} r={rung}"
                      f" evals={_st.get('n_children', 0)}"
                      f" expanded={_st.get('n_expanded', 0)}"
                      f" canon_uniq={_st.get('canon_unique', -1)}"
                      f" cuts={_st.get('cuts', 0)}"
                      f" emerg={1 if _st.get('emergency') else 0}",
                      flush=True)
        return best_obj, best_sol
    except Exception:
        return float("inf"), None


def _canary(_):
    """Trivial worker proving that process spawning works in THIS host
    before the budget is committed to the parallel path.  (GUI hosts
    re-import their main module in spawned children on Windows, which can
    hang every worker -- observed as a 500s run returning 60s-quality
    results, T=3865 on prob_38.)"""
    return 42


def spawn_works(timeout=10.0):
    try:
        from concurrent.futures import ProcessPoolExecutor
        ex = ProcessPoolExecutor(max_workers=1)
        try:
            return ex.submit(_canary, 0).result(timeout=timeout) == 42
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
    except Exception:
        return False


def _assign_map(sol):
    """(block_id -> bay_id) of a solution -- the only part of a losing
    worker's answer that T2/T4 reuse (the rest is discarded by min())."""
    try:
        m = {}
        for _t, ops in sol["operations"].items():
            for o in ops:
                if o["type"] == "ENTRY":
                    m[o["block_id"]] = o["bay_id"]
        return m
    except Exception:
        return None


def solve_parallel(prob_info, timelimit, configs, env):
    """Run up to 4 configs in parallel; return (best_obj, best_sol,
    assign_maps) -- maps of EVERY finishing worker (T2: the blocks the
    lenses DISAGREE on are the ideal ruin targets), or (inf, None, [])
    if every worker failed.  Returns by timelimit*0.78 at the latest,
    leaving the caller a rescue/post-pass window."""
    from concurrent.futures import (ProcessPoolExecutor, TimeoutError,
                                    as_completed)

    t0 = time.time()
    # [TR v19.9] ratio-banded triage constants, set in the MAIN process
    # (before spawn) so both the workers (env inheritance) and the main-
    # process ladder/reconstruction paths see the same constants.  Always
    # assigned explicitly (both branches) -- no cross-problem env leak.
    if os.environ.get("OGC_TRB", "1") == "1":
        try:
            _bl9 = prob_info["blocks"]
            _dm9 = max(b["due_date"] for b in _bl9)
            _ar9 = sum(b["width"] * b["height"] for b in prob_info["bays"])
            _de9 = 0.0
            for _b9 in _bl9:
                _vs9 = _b9["shape"][0]["layers"][0]
                _xs9 = [v[0] for v in _vs9]
                _ys9 = [v[1] for v in _vs9]
                _de9 += ((max(_xs9) - min(_xs9)) * (max(_ys9) - min(_ys9))
                         * _b9["processing_time"])
            _rt9 = _de9 / max(1e-9, _ar9 * _dm9)
            if _rt9 >= float(os.environ.get("OGC_TRB_HI", "1.02")):
                os.environ["OGC_TRIMULT"] = \
                    os.environ.get("OGC_TRB_M", "1.5")
                os.environ["OGC_TRIREL"] = "0.2"
            elif 0.9 <= _rt9 < float(os.environ.get("OGC_TRB_LO", "0.95")):
                os.environ["OGC_TRIMULT"] = "2.0"
                os.environ["OGC_TRIREL"] = \
                    os.environ.get("OGC_TRB_R", "0.1")
            else:
                os.environ["OGC_TRIMULT"] = "2.0"
                os.environ["OGC_TRIREL"] = "0.2"
        except Exception:
            pass
    # [예산재배분] construction<->improvement split is env-overridable for
    # the seat-economics A/B: the improvement loop is dead on many
    # instances (LNS imp=0 on large/tardy at all budgets; justify converges
    # in one round), so its budget (~0.78T-0.96T window) may be better
    # spent on construction (wider beams).  Default 0.68/0.78 unchanged.
    # [T1 v19.4] band-differential defaults: at the 500s band the ladder
    # window is dead capital ([FB]: justify gain 1/52 @500), so trade it
    # for construction width.  <300s bands keep 0.68/0.78 (B240 rejected:
    # 3 regressions; @60 untouched by rule).  Explicit env overrides all
    # bands (experiment path); collection margin fixed at 0.10T.
    _wbe = os.environ.get("OGC_WBUDGET")
    _wde = os.environ.get("OGC_WDEADLINE")
    if _wbe is not None:
        _wb = float(_wbe)
    elif os.environ.get("OGC_T1", "1") == "1" and timelimit >= 300:
        _wb = 0.78
    else:
        _wb = 0.68
    _wd = float(_wde) if _wde is not None else _wb + 0.10
    budget = timelimit * _wb           # per-worker solver budget
    deadline = t0 + timelimit * _wd    # global collection deadline
    best = (float("inf"), None)
    maps = []
    try:
        ex = ProcessPoolExecutor(max_workers=4)
        try:
            futs = [ex.submit(_worker, (prob_info, cfg, budget, env, wi))
                    for wi, cfg in enumerate(configs[:4])]
            try:
                for f in as_completed(
                        futs, timeout=max(5.0, deadline - time.time())):
                    try:
                        obj, sol = f.result(timeout=1.0)
                        if sol is not None:
                            m = _assign_map(sol)
                            if m:
                                maps.append(m)
                            if obj < best[0]:
                                best = (obj, sol)
                    except Exception:
                        pass
            except TimeoutError:
                pass  # stragglers forfeit; workers self-terminate by budget
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    return best[0], best[1], maps


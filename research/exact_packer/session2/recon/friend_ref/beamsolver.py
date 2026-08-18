# -*- coding: utf-8 -*-
"""
beamsolver.py -- multi-phase scoring + beam search over the full grid.

Per block (EDD order), per beam state:
  Phase 1: for every bay x orientation, find the EARLIEST feasible entry and
           the full set of feasible integer positions (FFT raster masks,
           conservative -> guaranteed crane/collision feasible).
  Phase 2: within each (bay, orient, entry), pick the best position by the
           spatial packing score (contact perimeter, then low top edge).
  Phase 3: compare candidates across bays with the TRUE objective delta:
           w1*tardiness + w2*obj2(updated loads) + w3*pref_penalty.
Beam search keeps the best B partial solutions ranked by cumulative
objective (obj1+obj3 accumulated, obj2 measured on current loads) with a
small spatial bonus; beam width adapts to the remaining time budget.
"""

from __future__ import annotations

import json
import math
import sys
import time

import numpy as np
from scipy.signal import fftconvolve
from scipy.ndimage import binary_dilation

from shapely.affinity import translate as _shp_translate

from gridsolver import (OrientGeo, S, TIGHT, orient_geo, _conv_count,
                        _build_operations, check_feasibility)

import os as _os
NATIVE = _os.environ.get("OGC_NATIVE", "0") == "1"
_CGLOG = _os.environ.get("OGC_CGLOG", "0") == "1"  # [CG1] print-only
_CGFIX = _os.environ.get("OGC_CGFIX", "0") == "1"  # [CG-BAY A1] guard fix
_CGBAY2 = _os.environ.get("OGC_CGBAY", "0") == "1"  # [CG-BAY A2] per-bay
_CGCAP = int(_os.environ.get("OGC_CGCAP", "2"))  # [CG-CAP] late cap arm
_EPSHADOW = _os.environ.get("OGC_EPSHADOW", "0") == "1"  # [EP1] shadow
_GCCAP = int(_os.environ.get("OGC_GCCAP", "1600"))  # [GC] cache cap arm
# how far down the position ranking the exact verifier walks in TIGHT mode
VERIFY_TRIES = int(_os.environ.get("OGC_VERIFY_TRIES", "12"))
# E2 (layer accounting): score-side occupancy = full vertical projection of
# resident blocks (union over layers) instead of layer 0 only.  Worker axis
# (env per worker; rung overrides set beamsolver.E_SH directly).
E_SH = _os.environ.get("OGC_ESH", "0") == "1"
# E3 (layer accounting): contact = sum over layers of per-layer ring
# adjacency (profile nesting scores its true adjacency).  Rung axis too.
E_CT = _os.environ.get("OGC_ECT", "0") == "1"
# P-A (packing, temporal coherence): contact counts only ALIGNED
# neighbours -- wall (never leaves) or |exit_p - exit_c| <= W with
# W = alpha * mean_proc.  Dedicated line (replaces contact, no mixing).
E_AL = _os.environ.get("OGC_EAL", "0") == "1"
EAL_ALPHA = float(_os.environ.get("OGC_EALW", "0.5"))
# P-B (packing, dead space): contact minus created-pocket count -- both
# in cells, knob-free.  Dedicated line as well.
E_PK = _os.environ.get("OGC_EPK", "0") == "1"
# [POS] top-p position branching: the sweep finds dozens-hundreds of
# feasible positions per (bay, entry, orient) but only 2 are emitted
# (best-score + bottom-left).  POSP>1 emits the top-POSP by score as
# separate children (canonical dedup absorbs true dups; near-dups are a
# dilution risk since canon includes px,py -- watched via canon_unique).
POSP = max(1, int(_os.environ.get("OGC_POSP", "1")))
# [TP] beam-width multiplier for the ceiling-hypothesis experiment
_WIDTHMUL = float(_os.environ.get("OGC_WIDTHMUL", "1"))
# [Morton/BP-cache] route base feasibility through pre-packed word-AND
# (packing amortized at grid_cache build).  byte-identical per rung + faster
# => more rungs fire in the budget => min() strictly non-regressing.  ON by
# default in v16; OGC_MORTON=0 reverts for A/B.
_MORTON = _os.environ.get("OGC_MORTON", "1") == "1" and NATIVE
# ^ [SUB1] Morton word-AND needs the native _pack_grid; without numba the
#   FFT path must run with _MORTON off (it referenced _pack_grid
#   unconditionally and NameError'd -- found by the numba-blocked drill).
# [F3] P-R (exit-release alignment): candidates whose exit lands near the
# release times of still-unplaced demand get a rank bonus, so space tends
# to open right when demand arrives.  Release times are INSTANCE
# CONSTANTS -- no estimation (the gz/gza/rollout rejections were all
# value-estimation lineages).  First version: instance-wide area-weighted
# release histogram (state-independent by design, cheaper and immune to
# mid-run drift); window derived P-A-style (alpha x mean_proc, no knob).
E_PR = _os.environ.get("OGC_EPR", "0") == "1"
# T1 A/B scaffolding (local only): revert to the pre-fix pruning form
T1_OFF = _os.environ.get("OGC_NOT1", "0") == "1"
# S0 per-item verification scaffolding (local only): revert S2 (eviction
# policy) / S5 (incremental bay hash) independently
S2_OFF = _os.environ.get("OGC_NOS2", "0") == "1"
S5_OFF = _os.environ.get("OGC_NOS5", "0") == "1"
_nk_verdict = None   # [EXN] numba fast verdict (loaded with the kernels)
if NATIVE:
    from native_kernel import sweep_positions as _native_sweep
    from native_kernel import sweep_positions_multi as _native_sweep_multi
    from native_kernel import (sweep_positions_pre as _native_sweep_pre,
                               pack_grid as _pack_grid)
    from native_kernel import poly_verdict as _nk_verdict
_EXN = _os.environ.get("OGC_EXN", "1") == "1"
# [CPP v20] C++ core.  OGC_CPP: position stage + scoring tail.
# OGC_CPPBP: C++ also owns the geo registry / grid build / grid cache /
# entries loop.  OGC_CPPCHK runs BOTH python and C++ per call and asserts
# bitwise equality.  OGC_CPP_FAIL injects failures to exercise fallback.
# Any import/call failure -> the original python path, unchanged.
_CPP = _os.environ.get("OGC_CPP", "0") == "1"
_CPPBP = _os.environ.get("OGC_CPPBP", "0") == "1"
_CPPCHK = _os.environ.get("OGC_CPPCHK", "0") == "1"
_CPPFAIL = _os.environ.get("OGC_CPP_FAIL", "0") == "1"


def _tight_nostop(entries, n_entry_opts):
    """C++ early-stop bound.  Under TIGHT the C++ cannot know whether
    _pick will reject every position of an entry (exact verification is
    python), so give it a bound it can never reach and let python own
    the n_found accounting."""
    return (len(entries) + 1) if TIGHT else int(n_entry_opts)
_ogc_core = None
_nk4cpp = None
if _CPP or _CPPBP or _CPPCHK:
    try:
        import ogc_core as _ogc_core
        import native_kernel as _nk4cpp
    except Exception:
        _ogc_core = None
        _CPP = _CPPBP = _CPPCHK = False
_eal_cov = True
_cpp_stat = [0, 0, 0]   # CHK: checked, mismatches, covered
_cpp_use = [0, 0]       # USE: bay_pass calls, score_bay calls  # [EXN] 3-tier fast exact_ok
# [HZ v19.8] future-Z1 lower-bound ranking term, lam=0.5.  Default OFF
# here -- parallel_multi turns it ON per worker via the demand-ratio BAND
# gate [0.95, 1.02): the gain (38 -3.03%, all-time) lives only near
# ratio ~= 1 (capacity binding, not hopeless); ratio > 1 (27 +2.15%) and
# lower ratios (40 +2.99%, 33/32 micro-drift) mislead the bound.  The
# seat-split alternative (HZ on loser seats W1/W2) measured 38 = base:
# the gain needs the winner (TIGHT) trajectories -> band is the only
# separating signal.
_HZ = _os.environ.get("OGC_HZ", "0") == "1"
_HZW = float(_os.environ.get("OGC_HZW", "0.5"))


_MEMOSHADOW = _os.environ.get("OGC_MEMOSHADOW", "0") == "1"  # [MEMO0]
_MEMO = _os.environ.get("OGC_MEMO", "1") == "1"  # [MEMO1] real memoization
_memo_seen: set = set()      # shadow key store (cleared per solve_beam)
_memo_stat = [0, 0]          # calls-with-sig, hits
_memo_cache: dict = {}       # [MEMO1] verdict cache (cleared per solve_beam)
# [S3 v19.5] signature grid reuse: on primary-key (bay_hash, entry) miss,
# a second content-signature lookup (occupants + per-occupant need_ge/
# need_le/resident flags + E_SH/occ_st/exq presence) reuses an equal grid
# built under a DIFFERENT (entry, block).  byte-identical (S3CHK-audited:
# line 5/5 + pipeline 6/6 exact); net line saving 4.9~9.4% -> +1..+2 rung
# firings @500 on 21/38/40.  resident flag (pa <= entry < pe) is REQUIRED:
# it is the occ0/occ_st/exq builder condition and is not implied by the
# need flags (단계0 audit).
_S3 = _os.environ.get("OGC_S3", "1") == "1"
_S3CHK = _os.environ.get("OGC_S3CHK", "0") == "1"  # audit: assert reuse==build
_s3_index: dict = {}  # sig -> grid tuple (aliases into grid_cache)


def _exact_ok(geo, px, py, bi, entry, exit_t, placed, geos, tcache,
              bay_w, bay_h, geos_lookup=None, memo_sig=None) -> bool:
    """Exact polygon-level feasibility of ONE placement under the crane
    j>=k rules (mirrors the mask build).  Used in TIGHT mode where the
    raster is not conservative."""
    if memo_sig is not None:
        _mk = (memo_sig, id(geo), px, py, entry, exit_t)
        if _MEMO:
            # [MEMO1] pure-function memoization: the key encodes every
            # input (sig covers placed; geos/bay are instance-static), so
            # same key = same verdict -- an identity, not a heuristic.
            _v = _memo_cache.get(_mk)
            if _v is not None:
                return _v
            if len(_memo_cache) > 2_000_000:  # RSS guard (~300MB);
                _memo_cache.clear()           # eviction measured harmless
            _r = _exact_ok_impl(geo, px, py, bi, entry, exit_t, placed,
                                geos, tcache, bay_w, bay_h, geos_lookup)
            _memo_cache[_mk] = _r
            return _r
        if _MEMOSHADOW:
            # [MEMO0] shadow gate: count hit/miss ONLY; verdict computed
            # as before -- zero behaviour change.
            _memo_stat[0] += 1
            if _mk in _memo_seen:
                _memo_stat[1] += 1
            else:
                _memo_seen.add(_mk)
    return _exact_ok_impl(geo, px, py, bi, entry, exit_t, placed, geos,
                          tcache, bay_w, bay_h, geos_lookup)


def _exact_ok_impl(geo, px, py, bi, entry, exit_t, placed, geos, tcache,
                   bay_w, bay_h, geos_lookup=None) -> bool:
    """Dispatch: [EXN] numba 3-tier when gated on and geometry qualifies,
    else the [EX] bbox-prefilter shapely path (v18.2 default)."""
    if not _EXN or _nk_verdict is None or geo.polys_v is None:
        return _exact_ok_core(geo, px, py, bi, entry, exit_t, placed,
                              geos, tcache, bay_w, bay_h, geos_lookup)
    # [EXN] v17.3 three-tier check per (layer, layer) pair:
    #   1) bbox pre-filter  2) numba poly_verdict SURE answers
    #   3) shapely intersection.area for the AMBIGUOUS remainder
    # Every tier is a sufficient/necessary condition of the exact test,
    # so the answer is byte-identical to the pure shapely version.
    va = geo.polys_v
    pbb = geo.pb
    K = geo.K
    fpx = float(px)
    fpy = float(py)
    minx = min(b[0] for b in pbb) + fpx
    miny = min(b[1] for b in pbb) + fpy
    maxx = max(b[2] for b in pbb) + fpx
    maxy = max(b[3] for b in pbb) + fpy
    if minx < -1e-9 or miny < -1e-9 or maxx > bay_w + 1e-9 \
            or maxy > bay_h + 1e-9:
        return False
    new_shp = None                        # lazy shapely for tier 3
    for (pb, po, ppx, ppy, pa, pe) in placed:
        if not ((pa < exit_t and pe > entry) or pe == exit_t):
            continue
        need_ge = (pa < entry < pe or (pa == entry and pb < bi)
                   or pa < exit_t < pe or (pe == exit_t and pb > bi))
        need_le = ((pa == entry and pb > bi)
                   or (pe == exit_t and pa < exit_t and pb < bi)
                   or entry < pa < exit_t or entry < pe < exit_t)
        key = (pb, po, ppx, ppy)
        ent = tcache.get(key)
        if ent is None:
            pg = geos_lookup(pb, po) if geos_lookup else geos[pb][po]
            # [EXN] cache the GEO (verts shared, no translate) + a lazy
            # shapely slot filled only if an AMBIGUOUS pair ever needs it
            ent = [pg, None]
            tcache[key] = ent
        pg = ent[0]
        vb = pg.polys_v
        if vb is None:                    # neighbour needs full shapely
            return _exact_ok_core(geo, px, py, bi, entry, exit_t, placed,
                                  geos, tcache, bay_w, bay_h, geos_lookup)
        ebb = pg.pb
        fqx = float(ppx)
        fqy = float(ppy)
        Ke = pg.K
        for k in range(K):
            if need_ge and need_le:
                js = range(Ke)
            elif need_ge:
                js = range(k, Ke)
            elif need_le:
                js = range(0, min(k, Ke - 1) + 1) if Ke else range(0)
            else:
                js = range(k, k + 1) if k < Ke else range(0)
            a = pbb[k]
            ax0 = a[0] + fpx
            ay0 = a[1] + fpy
            ax1 = a[2] + fpx
            ay1 = a[3] + fpy
            for j in js:
                b = ebb[j]
                if (ax1 <= b[0] + fqx or b[2] + fqx <= ax0
                        or ay1 <= b[1] + fqy or b[3] + fqy <= ay0):
                    continue              # tier 1: bbox disjoint
                v = _nk_verdict(va[k], fpx, fpy, vb[j], fqx, fqy)
                if v == 0:
                    continue              # tier 2: SURE area == 0
                if v == 1:
                    return False          # tier 2: SURE area > 0
                # tier 3: AMBIGUOUS -> exact shapely on lazily-built polys
                if new_shp is None:
                    new_shp = [_shp_translate(p, px, py) for p in geo.polys]
                if ent[1] is None:
                    ent[1] = [_shp_translate(p, ppx, ppy) for p in pg.polys]
                inter = new_shp[k].intersection(ent[1][j])
                if not inter.is_empty and inter.area > 0.0:
                    return False
    return True


def _exact_ok_core(geo, px, py, bi, entry, exit_t, placed, geos, tcache,
                   bay_w, bay_h, geos_lookup=None) -> bool:
    new_polys = [_shp_translate(p, px, py) for p in geo.polys]
    # [EX] bounds ONCE per poly: the old four min/max generator passes called
    # .bounds 4*K times, and the pre-filter below reuses the same tuples
    nb = [p.bounds for p in new_polys]
    # bay bounds (raster frame may under-cover the true bbox in TIGHT mode)
    if (min(b[0] for b in nb) < -1e-9 or min(b[1] for b in nb) < -1e-9
            or max(b[2] for b in nb) > bay_w + 1e-9
            or max(b[3] for b in nb) > bay_h + 1e-9):
        return False
    for (pb, po, ppx, ppy, pa, pe) in placed:
        if not ((pa < exit_t and pe > entry) or pe == exit_t):
            continue
        need_ge = (pa < entry < pe or (pa == entry and pb < bi)
                   or pa < exit_t < pe or (pe == exit_t and pb > bi))
        need_le = ((pa == entry and pb > bi)
                   or (pe == exit_t and pa < exit_t and pb < bi)
                   or entry < pa < exit_t or entry < pe < exit_t)
        # [EXN] distinct key suffix under the fast path so the two cache
        # entry formats ([pg, lazy] vs (ep, bounds)) never collide
        key = (pb, po, ppx, ppy, "shp") if _EXN else (pb, po, ppx, ppy)
        ent = tcache.get(key)
        if ent is None:
            pg = geos_lookup(pb, po) if geos_lookup else geos[pb][po]
            ep = [_shp_translate(p, ppx, ppy) for p in pg.polys]
            # [EX] cache each neighbour poly's bounds beside the poly so the
            # pre-filter never recomputes them (millions of .bounds calls)
            ent = (ep, [p.bounds for p in ep])
            tcache[key] = ent
        ep, eb = ent
        Ke = len(ep)
        for k, npoly in enumerate(new_polys):
            if need_ge and need_le:
                js = range(Ke)
            elif need_ge:
                js = range(k, Ke)
            elif need_le:
                js = range(0, min(k, Ke - 1) + 1) if Ke else range(0)
            else:
                js = range(k, k + 1) if k < Ke else range(0)
            a = nb[k]
            for j in js:
                # [EX] bbox pre-filter -- byte-identical, not a heuristic:
                # overlapping bboxes are a NECESSARY condition for
                # intersection area > 0.  If a's max_x <= b's min_x (etc.)
                # the overlap region is confined to a line, so its area is
                # exactly 0 -- precisely the case the exact test below would
                # NOT reject.  Skipping it therefore cannot change the
                # answer, and costs ~1/50 of building the intersection
                # geometry.  Measured: 91% of pairs are bbox-disjoint
                # (prob_38 6,920,692/7,565,652; prob_30 90.5%).
                b = eb[j]
                if (a[2] <= b[0] or b[2] <= a[0]
                        or a[3] <= b[1] or b[3] <= a[1]):
                    continue
                inter = npoly.intersection(ep[j])
                # checker rejects area > 0; geometry-library versions may
                # differ between local and server (FAQ), so reject ANY
                # positive intersection area -- strictly conservative
                if not inter.is_empty and inter.area > 0.0:
                    return False
    return True


# -----------------------------------------------------------------------------

class State:
    __slots__ = ("placed", "loads", "cum_hard", "cum_contact", "assignments",
                 "sig", "hist", "psig", "canon", "seq_sigs",
                 "cum_ct", "lens_mask", "cum_pr")

    def __init__(self, n_bays):
        self.placed = [[] for _ in range(n_bays)]
        self.loads = [0.0] * n_bays
        self.cum_hard = 0.0      # w1*sum(tardy) + w3*sum(prefpen)
        self.cum_contact = 0.0   # accumulated contact (higher = tighter)
        self.assignments = {}
        self.sig = 0             # incremental placement-sequence hash
        self.hist = []           # rank position among children at each step
        self.canon = 0           # order-independent placement-set hash (XOR)
        self.psig = 0            # parent's sig (per-parent beam quota)
        # S5: per-bay incremental sequence hash -- replaces the per-call
        # tuple(placed[bay]) rebuild in the grid-cache key (same key
        # semantics: chain hash is placement-sequence determined)
        self.seq_sigs = [0] * n_bays
        # [M] merged-lens mode: per-lens contact trajectory (the chosen
        # position's contact as seen by EVERY lens -- keeps each lens's
        # rank consistent over mixed-ancestry states) and the bitmask of
        # lens quotas this ancestry passed (crossbreeding evidence)
        self.cum_ct = None
        self.lens_mask = 0
        # [F3] P-R: accumulated release-histogram alignment of the chosen
        # placements' exits (beam-rank term, exact-objective untouched)
        self.cum_pr = 0.0

    def clone(self):
        s = State.__new__(State)
        s.placed = [list(b) for b in self.placed]
        s.loads = list(self.loads)
        s.cum_hard = self.cum_hard
        s.cum_contact = self.cum_contact
        s.assignments = dict(self.assignments)
        s.sig = self.sig
        s.hist = list(self.hist)
        s.psig = self.psig
        s.canon = self.canon
        s.seq_sigs = list(self.seq_sigs)
        s.cum_pr = self.cum_pr
        s.cum_ct = list(self.cum_ct) if self.cum_ct is not None else None
        s.lens_mask = self.lens_mask
        return s


ORDER_KEYS = {
    "edd":     lambda bd: (lambda i: (bd[i]["due_date"],
                                      bd[i]["processing_time"])),
    "release": lambda bd: (lambda i: (bd[i]["release_time"],
                                      bd[i]["due_date"])),
    "slack":   lambda bd: (lambda i: (bd[i]["due_date"] - bd[i]["release_time"]
                                      - bd[i]["processing_time"],
                                      bd[i]["due_date"])),
    "edd_big": lambda bd: (lambda i: (bd[i]["due_date"],
                                      -_shape_area(bd[i]))),
    # latest-start-time: how soon the block MUST enter to be on time --
    # more urgent than due date alone when processing times vary
    "lst":     lambda bd: (lambda i: (bd[i]["due_date"]
                                      - bd[i]["processing_time"],
                                      -_shape_area(bd[i]))),
    # due date, ties by space-time footprint (area x processing): the
    # blocks that consume the most bay capacity go first as anchors
    "edd_at":  lambda bd: (lambda i: (bd[i]["due_date"],
                                      -_shape_area(bd[i])
                                      * bd[i]["processing_time"])),
    # [TRI] triage order, reverse-engineered from the reference prob_38
    # solution (obj 35,749,260): its 25 heavy-late "victims" average 2.3x
    # the population area -- tardiness costs PER BLOCK while space costs
    # AREA x TIME, so in an overloaded rush a deferred big block (+50
    # tardy) frees room for 3-5 small on-time blocks.  edd_big/edd_at do
    # the OPPOSITE (big first).  Rule: blocks with area >= TRI_MULT x mean
    # go to the BACK (edd among themselves); the rest keep edd_big.
    # Fired ONLY by the overload-regime switch in parallel_multi.
    "edd_tri": lambda bd: (lambda i, _thr=(
        sum(_shape_area(b) for b in bd) / max(1, len(bd))
        * float(_os.environ.get("OGC_TRIMULT", "2.0"))):
        (1 if _shape_area(bd[i]) >= _thr else 0,
         bd[i]["due_date"], -_shape_area(bd[i]))),
    # [TRI2] selective triage, round 2 of the reference reverse engineering:
    # the reference SAVES big blocks released into a still-empty yard
    # (its 5 saved bigs: rel 1-9, entry == rel, tardy 0 -- free anchors)
    # and sacrifices only bigs releasing after the yard fills (rel >= 10,
    # all late).  Blanket edd_tri kills those early bigs too (+300 tardy
    # on prob_38 = the whole residual vs the reference).  Rule: defer a
    # big block ONLY if rel > rel_max x OGC_TRIREL (default 0.2 -- matches
    # the reference split exactly on 38: 47 x 0.2 = 9.4).  Measured line
    # level: 38 -3.2% (35,833,717, +0.24% off the reference) but 27/40
    # regress -> instance-dependent, so it rides a SEAT under min() (see
    # parallel_multi), never a global swap.
    "edd_tri2": lambda bd: (lambda i, _thr=(
        sum(_shape_area(b) for b in bd) / max(1, len(bd))
        * float(_os.environ.get("OGC_TRIMULT", "2.0"))),
        _r0=(max(b["release_time"] for b in bd)
             * float(_os.environ.get("OGC_TRIREL", "0.2"))):
        (1 if (_shape_area(bd[i]) >= _thr
               and bd[i]["release_time"] > _r0) else 0,
         bd[i]["due_date"], -_shape_area(bd[i]))),
}


def _shape_area(block_data):
    vs = block_data["shape"][0]["layers"][0]
    xs = [v[0] for v in vs]
    ys = [v[1] for v in vs]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def _obj2_now(loads, u):
    n = len(loads)
    if n < 2:
        return 0.0
    return max(abs(u[i] * loads[i] - u[j] * loads[j])
               for i in range(n) for j in range(n) if i != j)


def dispatch_order(bays_data, blocks_data):
    """[F1] time-major dispatch order: an event clock walks the timeline
    and emits blocks in the order a space-aware dispatcher would commit
    them, so a block whose hole opens at time t is sequenced near t
    instead of at its static-priority position.  Only the ORDER is kept
    -- the beam re-decides every position -- so the spatial model can
    stay crude (bbox-area accounting per bay, no geometry).  "early lst,
    late edd"-style switches emerge from the avail set changing over
    time; there is no schedule knob."""
    import heapq
    n, nb = len(blocks_data), len(bays_data)
    cap = [b["width"] * b["height"] for b in bays_data]
    used = [0.0] * nb
    area = [_shape_area(bd) for bd in blocks_data]
    rel = [bd["release_time"] for bd in blocks_data]
    due = [bd["due_date"] for bd in blocks_data]
    proc = [bd["processing_time"] for bd in blocks_data]
    remaining = set(range(n))
    exits = []  # (exit_time, bay, area) min-heap
    clock = min(rel)
    order = []
    while remaining:
        while exits and exits[0][0] <= clock:
            _, b, a = heapq.heappop(exits)
            used[b] -= a
        avail = sorted((i for i in remaining if rel[i] <= clock),
                       key=lambda i: (due[i] - proc[i] - clock, -area[i]))
        for i in avail:
            b = max(range(nb), key=lambda j: cap[j] - used[j])
            if area[i] <= cap[b] - used[b]:
                used[b] += area[i]
                heapq.heappush(exits, (clock + proc[i], b, area[i]))
                order.append(i)
                remaining.discard(i)
        if not remaining:
            break
        nxt = [t for t in (min((rel[i] for i in remaining
                                if rel[i] > clock), default=None),
                           exits[0][0] if exits else None) if t is not None]
        if nxt:
            clock = min(nxt)
        else:
            # everything released, nothing fits, nothing will exit:
            # force-commit the most urgent so the permutation completes
            i = min(remaining, key=lambda i: (due[i] - proc[i], -area[i]))
            b = max(range(nb), key=lambda j: cap[j] - used[j])
            used[b] += area[i]
            heapq.heappush(exits, (clock + proc[i], b, area[i]))
            order.append(i)
            remaining.discard(i)
    return order


# empirical cost model: seconds per (state, block) expansion is roughly
# proportional to the total bay area (grid units).  Measured on prob_1/21/38:
# 5.8e-6, 5.9e-6, ~5e-6 s/unit -- stable across instances on this machine.
# S-harvest: the S1/S3 uint8 pipeline measured 1.1-1.4x faster per
# expansion; the constant is env-tunable so the recalibration (speed ->
# WIDER rung-1 beams instead of idle slack) can be A/B tested.
K_COST = float(_os.environ.get("OGC_KCOST", "6e-6"))
B_MIN, B_MAX = 2, 192
# ^ [BXF] the v19.10 asset carried onto the full-C++ base.  96 was a
#   v1 unannotated constant that truncated prob_27@500's model demand
#   (b=318) to a third.  On the v19.9 base this was -0.93% over the
#   fired band; on THIS base it must be re-measured (a new base can
#   invert an asset -- see WIDTHMUL on the B192 base).
# ^ [BX v19.3] B_MAX=96 was an UNCOMMENTED v1-era literal (no measurement
#   trail, unlike K_COST above).  The ceiling audit showed it starving
#   non-overloaded @500 seats; parallel_multi lifts it to 192 per worker
#   when the TRI overload detector does NOT fire (fired instances keep 96
#   byte-identically -- their width path is KCLATE 4.0).  Measured @500:
#   29 -11.5% / 21 -10.2% / 25 -7.9% / 23 -7.8% / 24 -6.5%, fired trio
#   exactly unchanged.


def auto_beam_width(n_blocks: int, area_total: float,
                    timelimit: float) -> int:
    """Deterministic INITIAL beam width from problem size and budget.

    The beam narrows linearly with progress (see solve_beam): early blocks
    branch into many futures while late blocks are nearly forced moves, so
    search effort is front-loaded.  With a linear decay the average width is
    B0/2, which lets B0 start at 2x the flat-width budget equivalent."""
    # congestion factor: entry-candidate scans grow with blocks per bay;
    # (S/2)^2: FFT cost scales with raster resolution (K_COST measured at
    # S=2); TIGHT adds ~1.5x for exact polygon verification of picks
    est_state_cost = (K_COST * (S * S / 4.0) * (1.5 if TIGHT else 1.0)
                      * (0.6 if NATIVE else 1.0)   # fused numba sweep
                      * area_total * (0.5 + n_blocks / 200.0))
    b = int(2.0 * timelimit * 0.8 / max(1e-9, n_blocks * est_state_cost))
    # [TP] OGC_WIDTHMUL forces a wider beam than the budget model would pick,
    # to test the ceiling hypothesis: if diversity axes (POS etc.) revive at
    # a wider B, the bottleneck was width, not principle.  At a fixed budget
    # a wider beam is slower (may truncate via the emergency guard) -- use at
    # @500 only.  Default 1.0 = unchanged.
    b = int(b * _WIDTHMUL)
    return max(B_MIN, min(B_MAX, b))


def solve_beam(prob_info: dict, timelimit: float = 300.0,
               beam_init: int | None = None, cand_per_state: int = 6,
               n_entry_opts: int = 1, wait_mult: float = 20.0,
               order_name: str = "edd", rank_mode: str = "v0",
               pos_diverse: bool = False, schedule: str = "decay",
               pillar_q: float | None = None, pos_lam: float = 0.01,
               incumbent: float = float("inf"), ori_div: bool = False,
               fut_beta: float = 0.0,
               order_ids=None, anchor=None, merge: bool = False,
               snap_out=None, immigrants=None, snap_m: int = 3,
               verbose: bool = True):
    t0 = time.time()
    # [POS] activate the ALREADY-IMPLEMENTED but production-off diversity
    # mechanisms: pos_diverse (best-score + bottom-left position, 2 crit)
    # and ori_div (runner-up orientation).  All 4 workers ship pd=False and
    # ori_div defaults off, so production picks ONE position + ONE
    # orientation -- fully greedy on those axes.  Toggle to A/B whether the
    # existing 2-candidate mechanisms help before the top-p generalisation.
    if _os.environ.get("OGC_POSDIV") == "1":
        pos_diverse = True
    if _os.environ.get("OGC_ORIDIV") == "1":
        ori_div = True
    bays_data = prob_info["bays"]
    blocks_data = prob_info["blocks"]
    n_bays, n_blocks = len(bays_data), len(blocks_data)
    w1 = prob_info["weights"]["w1"]
    w2 = prob_info["weights"]["w2"]
    w3 = prob_info["weights"]["w3"]

    bay_W = [b["width"] for b in bays_data]
    bay_H = [b["height"] for b in bays_data]
    bay_areas = [w * h for w, h in zip(bay_W, bay_H)]
    avg_area = sum(bay_areas) / n_bays
    u = [avg_area / a for a in bay_areas]

    geos = [[orient_geo(sh["layers"]) for sh in bd["shape"]]
            for bd in blocks_data]
    KMAX = max(g.K for row in geos for g in row)  # instances have up to 4 layers
    _cpp_bp_ok = False
    if _CPPBP and _ogc_core is not None:
        try:                       # [CPP] one-time geometry registration
            _ogc_core.init_ctx(S, KMAX,
                               np.asarray(bay_W, np.int64),
                               np.asarray(bay_H, np.int64),
                               len(blocks_data), 1600)
            for _bi9, _gl9 in enumerate(geos):
                for _oi9, _g9 in enumerate(_gl9):
                    _ogc_core.register_geo(
                        _bi9, _oi9,
                        np.ascontiguousarray(_g9.masks_u8),
                        np.ascontiguousarray(
                            np.stack(_g9.masks_ge).astype(np.uint8)),
                        np.ascontiguousarray(
                            np.stack(_g9.masks_le).astype(np.uint8)),
                        _g9.ring_r, _g9.ring_c,
                        int(_g9.cx0), int(_g9.cy0), int(_g9.cells0),
                        float(_g9.bbox[0]), float(_g9.bbox[1]),
                        float(_g9.bbox[2]), float(_g9.bbox[3]),
                        float(_g9.top_h),
                        _g9.lring_r, _g9.lring_c, _g9.lring_off,
                        _g9.mv_r, _g9.mv_c, _g9.mv_off)
            _cpp_bp_ok = True
        except Exception:
            _cpp_bp_ok = False
    # P-A: alignment window in time units (alpha x mean processing time)
    W_AL = max(1, int(round(EAL_ALPHA
                            * sum(bd["processing_time"]
                                  for bd in blocks_data) / n_blocks)))
    # [M] merged-lens mode: stage-1 lenses = {base, P-A a=.25, P-A a=.5}
    _mp = sum(bd["processing_time"] for bd in blocks_data) / n_blocks
    W25 = max(1, int(round(0.25 * _mp)))
    W50 = max(1, int(round(0.50 * _mp)))
    N_LENS = 3
    merge = bool(merge) and NATIVE  # the fused kernel is native-only

    # [F3] P-R: area-weighted release histogram, smoothed over the P-A
    # window, normalised to [0,1]; looked up at a candidate's exit time.
    R_pr, pr_w = None, 0.0
    if E_PR:
        W_PR = max(1, int(round(0.25 * _mp)))
        T_PR = (max(bd["release_time"] for bd in blocks_data) + W_PR + 1)
        R_raw = [0.0] * (T_PR + 1)
        for bd in blocks_data:
            a = _shape_area(bd)
            r = bd["release_time"]
            for t in range(max(0, r - W_PR), min(T_PR, r + W_PR) + 1):
                R_raw[t] += a
        _mx = max(R_raw) or 1.0
        R_pr = [v / _mx for v in R_raw]
        # contact-scale by default; OGC_EPRW is VERIFICATION scaffolding
        # (dead-branch vs true-null discrimination), not a tuning knob
        pr_w = (1e-3 * min(w1, w3)
                * float(_os.environ.get("OGC_EPRW", "1")))
    pr_stat = [0, 0]  # [expansions scored, with cross-candidate R variance]

    # T4 (rung_G): an improved solution's entry-ascending block order makes
    # that solution reconstructible as ONE beam path (every "vacated slot"
    # predecessor is placed first) -- a path the heuristic orders' trees do
    # not contain.  anchor = its (block -> bay) map, rewarded SOFTLY in the
    # candidate score (a hard anchor would just copy the solution; the
    # value is in deviating near the path and re-adapting everything after)
    if order_ids is not None:
        order = list(order_ids)
    elif order_name == "dispatch":  # [F1] generated, not a sort key
        order = dispatch_order(bays_data, blocks_data)
    else:
        order = sorted(range(n_blocks),
                       key=ORDER_KEYS[order_name](blocks_data))
    # [F4] snapshot depths: quartiles of the ORDER (identical across the
    # rungs that share it, which is what makes transplanted states legal)
    _snap_depths = ({n_blocks // 4, n_blocks // 2, (3 * n_blocks) // 4}
                    - {0}) if snap_out is not None else set()
    anchor_w = 0.5 * w3  # soft: half a preference-penalty unit, no tuning

    # pillar mode: blocks with footprint area above the pillar_q quantile are
    # "large" -- their positions are steered to wall-flush stacked columns so
    # the bay centre stays contiguous for small blocks.
    is_large = [False] * n_blocks
    due_med = 0.0
    if pillar_q is not None:
        areas = sorted(_shape_area(bd) for bd in blocks_data)
        thr = areas[min(n_blocks - 1, int(pillar_q * n_blocks))]
        is_large = [_shape_area(bd) >= thr for bd in blocks_data]
        dues = sorted(bd["due_date"] for bd in blocks_data)
        due_med = dues[n_blocks // 2]

    # contact scale so it never dominates hard objective terms
    # ---- rank-score variants (candidate ranking / beam ranking) -------------
    # v0        : baseline  (full obj2-now, contact bonus mu)
    # ramp      : obj2 penalty ramps with progress -- early imbalance is
    #             tolerated because later blocks can even it out
    # hi_contact: 5x contact weight -- packing quality first
    # no_contact: contact used only for position choice, not for ranking
    RANK_MODES = {
        # (mu_mult, o2_mode): o2_mode = how the mid-run L-imbalance (obj2)
        # enters the search score -- "full" (w2 as-is), "ramp" (w2 x
        # progress), "off" (ignored during search; the final pick still uses
        # the exact objective)
        "v0":         (1.0, "full"),
        "ramp":       (1.0, "ramp"),
        "noL":        (1.0, "off"),
        "gh":         (1.0, "gh"),    # admissible h: reachable min imbalance
        "gz":         (1.0, "gz"),    # gh + fractional-capacity Z1 guidance
        "hi_contact": (5.0, "full"),
        "no_contact": (0.0, "full"),
    }
    mu_mult, o2_mode = RANK_MODES[rank_mode]
    mu = 1e-3 * min(w1, w3) * mu_mult
    mu_pos = 1e-3 * min(w1, w3)  # position choice always uses base contact
    wait_w = mu_pos * wait_mult  # penalty per time unit of voluntary waiting
    progress = 0.0               # fraction of blocks placed (updated in loop)

    def _o2w() -> float:
        if o2_mode in ("off", "gh"):
            return 0.0
        return w2 * (progress if o2_mode == "ramp" else 1.0)

    # D2: admissible h for the imbalance term.  Remaining workload W_rem,
    # if split arbitrarily (divisible relaxation), can raise the lighter
    # bays' levels v_i = u_i * L_i by waterfilling; the REACHABLE minimum of
    # max_ij |v_i - v_j| is a true lower bound on the final obj2 -- unlike
    # the current-imbalance term (overestimates, punishes fixable gaps) or
    # ignoring it (underestimates).
    W_rem = 0.0  # workload of not-yet-placed blocks (updated per step)

    def _h_obj2(loads) -> float:
        v = sorted((u[i] * loads[i], u[i]) for i in range(n_bays))
        vmax = v[-1][0]
        rem = W_rem
        # waterfill the lower levels up toward vmax
        level = v[0][0]
        caps = 0.0  # sum of 1/u for bays at `level`
        idx = 0
        while rem > 1e-12 and level < vmax - 1e-12:
            while idx < n_bays and v[idx][0] <= level + 1e-12:
                caps += 1.0 / v[idx][1]
                idx += 1
            nxt = v[idx][0] if idx < n_bays else vmax
            nxt = min(nxt, vmax)
            need = (nxt - level) * caps
            if need >= rem:
                level += rem / caps if caps > 0 else 0.0
                rem = 0.0
            else:
                rem -= need
                level = nxt
        return max(0.0, vmax - level) if n_bays >= 2 else 0.0

    # D2: fractional-capacity Z1 guidance.  The remaining blocks (due-sorted
    # cumulative area-time demand, precomputed per step) are assigned
    # fractionally to the state's FREE capacity integral F(t); the k-th
    # estimated completion F^-1(D_k) past due_k signals future tardiness the
    # exact g cannot see yet.  Guidance only -- NOT used in the pruning
    # bound (EDD pairing + area relaxation is not provably admissible).
    step_demands: list = []   # [(due_k, cumdem_k)] due-sorted, per step
    step_meta = [0.0, 1.0]    # [min release of remaining, avg block area]
    area_total_c = float(sum(bay_areas))

    def _h_z1(st: State, extra=None) -> float:
        if not step_demands:
            return 0.0
        events = []
        for bay in st.placed:
            for (_b, _o, _x, _y, a, e) in bay:
                # approximate each block's occupancy by its bay share
                events.append((a, 1.0))
                events.append((e, -1.0))
        if extra is not None:
            events.append((extra[0], 1.0))
            events.append((extra[1], -1.0))
        events.sort()
        # free-capacity integral; occupancy weight = avg block area
        t_now = step_meta[0]  # min release of remaining
        avg_a = step_meta[1]
        F = 0.0
        occ = 0.0
        t_prev = t_now
        idx = 0
        # advance events before t_now
        while idx < len(events) and events[idx][0] <= t_now:
            occ += events[idx][1]
            idx += 1
        tardy = 0.0
        k = 0
        n_dem = len(step_demands)
        t = t_now
        while k < n_dem:
            due_k, D_k = step_demands[k][0], step_demands[k][1]
            cap = max(area_total_c * 0.15,
                      area_total_c - occ * avg_a)  # free area rate
            nxt = events[idx][0] if idx < len(events) else float("inf")
            need_t = (D_k - F) / cap
            if t + need_t <= nxt:
                tau = t + need_t
                tardy += max(0.0, tau - due_k)
                k += 1
                F = D_k
                # do not advance t past tau -- next demand continues
                if tau > t:
                    t = tau
            else:
                F += cap * (nxt - t)
                t = nxt
                occ += events[idx][1]
                idx += 1
        return w1 * tardy

    def rank(st: State) -> float:
        h = w2 * _h_obj2(st.loads) if o2_mode in ("gh", "gz") else \
            _o2w() * _obj2_now(st.loads, u)
        if o2_mode == "gz":
            h += _h_z1(st)
        if _HZ:
            # [HZ v19.8] future-Z1 lower-bound term (lam*=0.5, user).
            # Self-gating: h_Z1 = 0 on non-overloaded states (73/73 rungs
            # measured) -> non-TRI classes byte-identical without a gate.
            # TRI-trio @500: 38 -3.03% (all-time best, beats reference by
            # -4.3%) / 27 +2.15% / 40 +2.99% -> class sum -0.82%.
            h += _HZW * _h_z1(st)
        # [F3] P-R enters HERE, not at candidate d_rank: with 2-4 bays the
        # candidate stage is bay-exhaustive (cands <= cap), so a candidate-
        # only term never selects anything -- measured: EPRW=1e9 changed
        # nothing while 25% of expansions had cross-candidate variance
        return (st.cum_hard + h - mu * st.cum_contact
                - pr_w * st.cum_pr)

    # ---- candidate generation for one (state, block) -------------------------
    # fast=True (emergency): preferred bay only, no contact scoring, first
    # bottom-left feasible position -- ~6x cheaper per block, used to finish
    # the tail inside the timelimit.
    def gen_candidates(st: State, bi: int, fast: bool = False):
        bd = blocks_data[bi]
        r_time = int(bd["release_time"])
        due = bd["due_date"]
        proc = int(bd["processing_time"])
        workload = bd["workload"]
        prefs = bd["bay_preferences"]
        s_max = max(prefs)

        cands = []  # (delta_rank, contact, bay, oi, px, py, entry)

        bays_iter = ([max(range(n_bays), key=lambda j: prefs[j])] if fast
                     else range(n_bays))
        for bay_id in bays_iter:
            W, H = bay_W[bay_id], bay_H[bay_id]
            GW, GH = W * S, H * S
            entries = sorted({r_time} | {e for (_, _, _, _, a, e)
                                         in st.placed[bay_id] if e > r_time})
            # cross-state cache key: identical bay contents (sequence hash)
            # + same block being placed => identical blocked grids
            # (S5: incremental per-bay chain hash instead of rebuilding
            # tuple(placed) on every (state, bay, block) visit)
            if S5_OFF:  # pre-S5 key (A/B baseline only)
                bay_hash = hash((bi, bay_id, tuple(st.placed[bay_id])))
            else:
                bay_hash = hash((bi, bay_id, st.seq_sigs[bay_id]))
            bay_best = []  # (contact, px, py, oi, entry) winners in this bay
            # [CPP] covered = the plain non-merge / non-TIGHT / no-lens
            # path the C++ port mirrors exactly; anything else stays python.
            # [E_CT] the layered lens is ported (per-layer occupancy +
            # ct_rc_l), so it no longer forces a python fallback.
            # [E_AL] ported (exq + sparse verify + aligned contact),
            # so the last measured fallback source is closed.  E_PK stays
            # out (unused in production) and merge/fast keep python.
            # [TIGHT] the tight raster only changes MASK CONSTRUCTION
            # (python, already registered) and the exact-verify inside
            # _pick (python, unchanged) -- the C++ sweep consumes whatever
            # masks it was given, so TIGHT needs no kernel work.
            _bp_cov = (_cpp_bp_ok and not merge and not fast
                       and not E_PK
                       and not _EPSHADOW
                       and _nk4cpp is not None and _nk4cpp._MC
                       and not _nk4cpp._MCCHK)
            if _bp_cov:
                _pl9 = st.placed[bay_id]
                _np9 = len(_pl9)
                _pb9 = np.fromiter((t[0] for t in _pl9), np.int64, _np9)
                _po9 = np.fromiter((t[1] for t in _pl9), np.int64, _np9)
                _pq9 = np.fromiter((t[2] for t in _pl9), np.int64, _np9)
                _pr9 = np.fromiter((t[3] for t in _pl9), np.int64, _np9)
                _pa9 = np.fromiter((t[4] for t in _pl9), np.int64, _np9)
                _pe9 = np.fromiter((t[5] for t in _pl9), np.int64, _np9)

            for oi, geo in enumerate(geos[bi]):
                n_found = 0
                # candidate ranges: raster frame AND exact polygon bounds
                # (in TIGHT mode the trimmed frame can under-cover the bbox)
                px_lo = max(math.ceil(-geo.cx0 / S),
                            math.ceil(-geo.bbox[0] - 1e-9))
                px_hi = min((GW - geo.nx - geo.cx0) // S,
                            math.floor(W - geo.bbox[2] + 1e-9))
                py_lo = max(math.ceil(-geo.cy0 / S),
                            math.ceil(-geo.bbox[1] - 1e-9))
                py_hi = min((GH - geo.ny - geo.cy0) // S,
                            math.floor(H - geo.bbox[3] + 1e-9))
                if px_lo > px_hi or py_lo > py_hi:
                    continue

                _bp_map = None
                if _bp_cov:
                    if geo.ny > GH or geo.nx > GW:
                        continue   # == python's break on the first entry
                    try:
                        if _CPPFAIL:
                            raise RuntimeError("CPP_FAIL injected")
                        _cpp_use[0] += 1
                        (_en3, _st3, _off3, _occ3, _px3, _py3, _ct3b,
                         _sc3) = _ogc_core.bay_pass(
                            int(bay_id), int(bi), int(oi), int(bay_hash),
                            np.asarray(entries, np.int64),
                            _pb9, _po9, _pq9, _pr9, _pa9, _pe9,
                            int(proc), int(bool(E_SH)),
                            int(bool(_MORTON)), int(bool(E_CT)),
                            int(bool(E_AL)), int(W_AL),
                            _tight_nostop(entries, n_entry_opts),
                            int(px_lo), int(px_hi), int(py_lo),
                            int(py_hi), int(1 if is_large[bi] else 0),
                            float(due), float(due_med), float(pos_lam),
                            float(fut_beta), float(mean_proc))
                        _bp_map = {}
                        for _ei3 in range(len(_en3)):
                            if _st3[_ei3] == 1:
                                _sl3 = slice(int(_off3[_ei3]),
                                             int(_off3[_ei3 + 1]))
                                _bp_map[int(_en3[_ei3])] = (
                                    _px3[_sl3], _py3[_sl3],
                                    _ct3b[_sl3], _sc3[_sl3])
                            else:
                                _bp_map[int(_en3[_ei3])] = None
                    except Exception:
                        _bp_map = None       # fall back to python below
                for entry in entries:
                    exit_t = entry + proc
                    _cpp_sc = None
                    if _bp_map is not None:
                        _r3 = _bp_map.get(int(entry), False)
                        if _r3 is False:
                            break       # C++ stopped at n_entry_opts
                        if _r3 is None:
                            continue    # area gate / empty sweep
                        pxs, pys, contact, _cpp_sc = _r3
                        ct3 = None
                    if _bp_map is None:
                        cache_key = (bay_hash, entry)
                        if cache_key in grid_cache:
                            grid_hits[0] += 1
                        else:
                            grid_hits[1] += 1
                            # S2: uint8 entries are ~4x smaller (S3), so the cap
                            # rises 400 -> 1600 (~300MB/worker worst case), and
                            # eviction drops the OLDEST half (dict = insertion
                            # order) instead of clearing everything -- a full
                            # clear made every sibling miss at once, exactly in
                            # the late-run phase where rebuilds are dearest
                            if S2_OFF:  # pre-S2 policy (A/B baseline only)
                                if len(grid_cache) > 400:
                                    grid_cache.clear()
                            elif len(grid_cache) > _GCCAP:
                                for old_k in list(grid_cache.keys())[:_GCCAP // 2]:
                                    del grid_cache[old_k]
                                grid_hits[2] += 1  # [GC] eviction events
                                if _S3:  # [S3] aliases into evicted entries
                                    _s3_index.clear()  # must not outlive them
                            # S3 (speed, behavior-preserving): stacked uint8
                            # built with |= -- the only downstream use is a >0
                            # test, and the cache then holds sweep-ready input
                            # (S1: no per-call stack/astype on cache hits)
                            # [S3 v19.5] 2-tier: signature lookup before build.
                            _s3v = _s3sig = None
                            if _S3:
                                _s3sig = (bay_id, E_SH, E_CT,
                                          (E_AL or merge), tuple(sorted(
                                    (pb2, po2, px2, py2, pa2, pe2,
                                     (pa2 < entry < pe2
                                      or (pa2 == entry and pb2 < bi)
                                      or pa2 < exit_t < pe2
                                      or (pe2 == exit_t and pb2 > bi)),
                                     ((pa2 == entry and pb2 > bi)
                                      or (pe2 == exit_t and pa2 < exit_t
                                          and pb2 < bi)
                                      or entry < pa2 < exit_t
                                      or entry < pe2 < exit_t),
                                     pa2 <= entry < pe2)
                                    for (pb2, po2, px2, py2, pa2, pe2)
                                    in st.placed[bay_id]
                                    if (pa2 < exit_t and pe2 > entry)
                                    or pe2 == exit_t)))
                                _s3v = _s3_index.get(_s3sig)
                            if _s3v is not None and not _S3CHK:
                                grid_cache[cache_key] = _s3v
                            else:
                                blocked = np.zeros((KMAX, GH, GW), dtype=np.uint8)
                                occ0 = np.zeros((GH, GW), dtype=np.uint8)
                                occ_st = (np.zeros((KMAX, GH, GW), dtype=np.uint8)
                                          if E_CT else None)
                                exq = (np.full((GH, GW), -1, dtype=np.int32)
                                       if (E_AL or merge) else None)  # P-A exits
                                for (pb, po, ppx, ppy, pa, pe) in st.placed[bay_id]:
                                    if not ((pa < exit_t and pe > entry) or pe == exit_t):
                                        continue
                                    pg = geos[pb][po]
                                    gx = ppx * S + pg.cx0
                                    gy = ppy * S + pg.cy0
                                    need_ge = need_le = False
                                    if pa < entry < pe or (pa == entry and pb < bi):
                                        need_ge = True
                                    if pa == entry and pb > bi:
                                        need_le = True
                                    if pa < exit_t < pe or (pe == exit_t and pb > bi):
                                        need_ge = True
                                    if pe == exit_t and pa < exit_t and pb < bi:
                                        need_le = True
                                    if entry < pa < exit_t or entry < pe < exit_t:
                                        need_le = True
                                    sl = (slice(gy, gy + pg.ny), slice(gx, gx + pg.nx))
                                    if need_ge:
                                        for k in range(min(KMAX, pg.K)):
                                            blocked[k][sl] |= pg.masks_ge[k]
                                    if need_le:
                                        for k in range(KMAX):
                                            blocked[k][sl] |= pg.masks_le[min(k, pg.K - 1)]
                                    if not (need_ge or need_le):
                                        for k in range(min(KMAX, pg.K)):
                                            blocked[k][sl] |= pg.masks[k]
                                    if pa <= entry < pe:
                                        # E2: ground under a resident's overhang is
                                        # sealed for new entries during its stay
                                        # (crane rule) -- the contact score must not
                                        # treat it as open ground.  Score-only; the
                                        # feasibility masks stay layer-exact so
                                        # legal safe nesting is unaffected.
                                        if E_SH:
                                            for k in range(pg.K):
                                                occ0[sl] |= pg.masks[k]
                                        else:
                                            occ0[sl] |= pg.masks[0]
                                        if occ_st is not None:  # E3 per-layer occ
                                            for k in range(pg.K):
                                                occ_st[k][sl] |= pg.masks[k]
                                        if exq is not None:  # P-A: exit-time grid
                                            _v = exq[sl]
                                            _v[pg.masks[0]] = pe
                                occ_cells = int((blocked[0] > 0).sum())
                                # [Morton/BP-cache] pack blocked to words ONCE here
                                # (reused across all orientations + revisits of this
                                # (bay, entry) state) so the sweep pays no packing.
                                blocked_w = (_pack_grid(blocked, KMAX,
                                                        (GW + 63) // 64 + 1)
                                             if _MORTON else None)
                                _gv = (blocked, occ0, occ_st,
                                       exq, occ_cells, blocked_w)
                                if _s3v is not None:  # _S3CHK audit path
                                    if not (np.array_equal(blocked, _s3v[0])
                                            and np.array_equal(occ0, _s3v[1])
                                            and (occ_st is None) == (_s3v[2] is None)
                                            and (occ_st is None
                                                 or np.array_equal(occ_st, _s3v[2]))
                                            and (exq is None) == (_s3v[3] is None)
                                            and (exq is None
                                                 or np.array_equal(exq, _s3v[3]))
                                            and occ_cells == _s3v[4]):
                                        raise AssertionError(
                                            "S3CHK grid mismatch (bay %s)" % bay_id)
                                    grid_cache[cache_key] = _s3v
                                else:
                                    grid_cache[cache_key] = _gv
                                    if _S3:
                                        _s3_index[_s3sig] = _gv
                        blocked, occ0, occ_st, exq, occ_cells, blocked_w = \
                            grid_cache[cache_key]

                        # cheap area gate: not enough free layer-0 cells -> skip FFT
                        if geo.cells0 > GH * GW - occ_cells:
                            continue

                        if geo.ny > GH or geo.nx > GW:
                            break  # orientation cannot fit this bay at all

                        ct3 = None
                        if NATIVE and merge and not fast:
                            # [M] fused multi-lens sweep: one feasibility pass,
                            # three lens contacts at once
                            pxs, pys, ct3 = _native_sweep_multi(
                                blocked, geo, S, px_lo, px_hi, py_lo, py_hi,
                                occ0, exq, exit_t, W25, W50)
                            if len(pxs) == 0:
                                continue
                            contact = ct3[0]
                        elif (_MORTON and blocked_w is not None and not fast
                              and geo.K <= 2
                              and not E_CT and not E_AL and not E_PK):
                            # [Morton/BP-cache] base path, K<=2 only.  On K>=3
                            # (multilayer) the per-word AND's 4-layer overhead
                            # outweighs the early-exit cell loop -> slower ->
                            # fewer rungs fire.  Confirmed catastrophic on the
                            # largest multilayer bay: OGC_SWK4 A/B gave prob_40@60
                            # 2,199,044 -> 4,844,533 (+120%).  [SW] doc's layer/row
                            # skip cannot fix it: measured 0% all-zero layers on
                            # every K=4 block, so there is nothing to skip.
                            # word-AND feasibility on pre-packed blocked; contact
                            # unchanged (byte-identical vs the base sweep).
                            _cpp_ok = False
                            if (_CPP and not _CPPCHK and not merge and not fast
                                    and _nk4cpp is not None and _nk4cpp._MC
                                    and not _nk4cpp._MCCHK):
                                try:
                                    if _CPPFAIL:
                                        raise RuntimeError("CPP_FAIL")
                                    _cpp_use[1] += 1
                                    pxs, pys, contact, _cpp_sc = \
                                        _ogc_core.select_words(
                                            blocked_w, geo.masks_w, geo.K,
                                            geo.ny, geo.nx, S, geo.cx0,
                                            geo.cy0, px_lo, px_hi, py_lo,
                                            py_hi, occ0, geo.ring_r,
                                            geo.ring_c, 1,
                                            int(1 if is_large[bi] else 0),
                                            float(due), float(due_med),
                                            float(geo.top_h), float(pos_lam),
                                            float(fut_beta), float(proc),
                                            float(mean_proc))
                                    _cpp_ok = True
                                except Exception:
                                    _cpp_sc = None
                            if not _cpp_ok:
                                pxs, pys, contact = _native_sweep_pre(
                                    blocked_w, geo, S, px_lo, px_hi, py_lo,
                                    py_hi, occ0, do_contact=not fast)
                            if len(pxs) == 0:
                                continue
                        elif NATIVE:
                            # fused native sweep: feasibility + contact in one
                            # compiled pass over lattice positions only
                            pxs, pys, contact = _native_sweep(
                                blocked, geo, S, px_lo, px_hi, py_lo, py_hi,
                                occ0, do_contact=not fast,
                                occ_st=occ_st if E_CT and not fast else None,
                                exq=exq if E_AL and not fast else None,
                                exit_c=exit_t, w_al=W_AL,
                                pk=E_PK and not fast)
                            if len(pxs) == 0:
                                continue
                        else:
                            tot = None
                            fit = True
                            for k in range(geo.K):
                                # non-native fallback path: fft needs float input
                                c = _conv_count(blocked[k].astype(np.float32),
                                                geo.masks_f32[k])
                                if c is None:
                                    fit = False
                                    break
                                tot = c if tot is None else tot + c
                            if not fit:
                                break

                            gys = np.arange(py_lo, py_hi + 1) * S + geo.cy0
                            gxs = np.arange(px_lo, px_hi + 1) * S + geo.cx0
                            feas = tot[np.ix_(gys, gxs)] < 0.5
                            if not feas.any():
                                continue

                            iy, ix = np.nonzero(feas)
                            pys = iy + py_lo
                            pxs = ix + px_lo

                        # Phase 2: contact + low-top position choice
                        if fast:
                            contact = np.zeros(len(pxs))
                        elif not NATIVE:
                            if E_CT and occ_st is not None:
                                contact = np.zeros(len(pxs))
                                for k in range(geo.K):
                                    rk = geo.rings_u8[k].astype(np.float32)
                                    ext = np.ones((GH + 2, GW + 2),
                                                  dtype=np.float32)
                                    ext[1:-1, 1:-1] = np.minimum(occ_st[k], 1.0)
                                    conv = fftconvolve(ext, rk[::-1, ::-1],
                                                       mode="valid")
                                    contact = contact + conv[pys * S + geo.cy0,
                                                             pxs * S + geo.cx0]
                            else:
                                ring = geo.ring_f32
                                ext = np.ones((GH + 2, GW + 2), dtype=np.float32)
                                ext[1:-1, 1:-1] = np.minimum(occ0, 1.0)
                                conv = fftconvolve(ext, ring[::-1, ::-1],
                                                   mode="valid")
                                contact = conv[pys * S + geo.cy0,
                                               pxs * S + geo.cx0]

                    def _pick(sc_arr):
                        """argmin of sc_arr; in TIGHT mode, exact-verify and
                        walk down the ranking until a position passes."""
                        order_idx = np.argsort(sc_arr)
                        tries = min(len(order_idx), VERIFY_TRIES) if TIGHT else 1
                        for jj in order_idx[:tries]:
                            if not TIGHT or _exact_ok(
                                    geo, int(pxs[jj]), int(pys[jj]), bi,
                                    entry, exit_t, st.placed[bay_id], geos,
                                    tcache, W, H,
                                    memo_sig=(st.seq_sigs[bay_id], bay_id,
                                              bi) if (_MEMOSHADOW or _MEMO) else None):
                                return int(jj)
                        return None

                    def _pick_topp(sc_arr, p):
                        """[POS] up to p exact-verified positions by ascending
                        score.  Non-TIGHT: every swept position is feasible ->
                        first p.  TIGHT: walk the ranking (cap VERIFY_TRIES*p)
                        collecting p that pass exact verification."""
                        order_idx = np.argsort(sc_arr)
                        if not TIGHT:
                            return [int(x) for x in order_idx[:p]]
                        out = []
                        cap = min(len(order_idx), VERIFY_TRIES * p)
                        for jj in order_idx[:cap]:
                            if _exact_ok(geo, int(pxs[jj]), int(pys[jj]), bi,
                                         entry, exit_t, st.placed[bay_id],
                                         geos, tcache, W, H,
                                         memo_sig=(st.seq_sigs[bay_id],
                                                   bay_id, bi)
                                         if (_MEMOSHADOW or _MEMO) else None):
                                out.append(int(jj))
                                if len(out) >= p:
                                    break
                        return out

                    if _cpp_sc is not None:
                        sc = _cpp_sc
                    elif is_large[bi]:
                        # pillar placement with TEMPORAL zoning: early-due
                        # large blocks go to the left wall, late-due to the
                        # right, stacked bottom-up -- columns whose blocks
                        # share similar exit times empty together, freeing
                        # contiguous space instead of scattered holes.
                        gx0 = pxs * S + geo.cx0
                        if due <= due_med:
                            wall_d = gx0
                        else:
                            wall_d = GW - (gx0 + geo.nx)
                        sc = wall_d * 1e6 + pys * 1000.0 - contact
                    else:
                        # pos_lam trades contact for a lower top edge:
                        # 0.01 ~ lexicographic (contact first);  larger values
                        # accept less contact to keep the skyline low
                        sc = (-contact + (pys + geo.top_h) * pos_lam
                              + pxs * pos_lam * 0.01)
                        if fut_beta > 0.0:
                            # future-value penalty: a long-staying block
                            # parked deep in the bay centre erases the most
                            # future placement options -- penalise wall
                            # distance in proportion to processing time
                            gx0 = pxs * S + geo.cx0
                            gy0 = pys * S + geo.cy0
                            dwall = np.minimum(
                                np.minimum(gx0, GW - (gx0 + geo.nx)),
                                np.minimum(gy0, GH - (gy0 + geo.ny))) / S
                            sc = sc + fut_beta * (proc / mean_proc) * dwall
                    if merge and not fast and ct3 is not None:
                        # [M] per-lens position choice: shared skyline/beta
                        # terms + each lens's own contact.  Lenses agreeing
                        # on a position merge naturally at emit-dedup.
                        shared = sc + contact  # sc without its -ct term
                        rn = float(geo.ring_f32.sum())
                        for l in range(N_LENS):
                            jl = _pick(shared - ct3[l])
                            if jl is None:
                                continue
                            vec = (float(ct3[0][jl]), float(ct3[1][jl]),
                                   float(ct3[2][jl]))
                            bay_best.append((vec[l], int(pxs[jl]),
                                             int(pys[jl]), oi, entry,
                                             rn, vec))
                        n_found += 1
                        if n_found >= n_entry_opts:
                            break
                        continue
                    # ring size normalises the wait-gate contact comparison;
                    # E3 contact sums K rings, so the norm must match
                    ring_norm = (float(geo.rings_u8.sum())
                                 if E_CT else float(geo.ring_f32.sum()))
                    if POSP > 1:  # [POS] top-p score positions
                        js = _pick_topp(sc, POSP)
                        if not js:
                            continue
                        for jj in js:
                            bay_best.append((float(contact[jj]), int(pxs[jj]),
                                             int(pys[jj]), oi, entry,
                                             ring_norm))
                        j = js[0]
                    else:
                        j = _pick(sc)
                        if j is None:
                            continue  # no exact-feasible position here
                        js = (j,)
                        bay_best.append((float(contact[j]), int(pxs[j]),
                                         int(pys[j]), oi, entry, ring_norm))
                    # position variant: strict bottom-left (spatial diversity
                    # for the beam -- same bay/entry, different geometry)
                    # pos_diverse: True (always) | "early" (first 40% of the
                    # run, where branching is scarce and decisions cascade)
                    pd_on = pos_diverse is True or (pos_diverse == "early"
                                                    and progress < 0.4)
                    j2 = _pick(pys * 100000.0 + pxs) if pd_on else j
                    if j2 is not None and j2 not in js:
                        bay_best.append((float(contact[j2]), int(pxs[j2]),
                                         int(pys[j2]), oi, entry, ring_norm))
                    n_found += 1
                    if n_found >= n_entry_opts:
                        break  # collected enough entry alternatives

            if not bay_best:
                continue
            if merge and not fast:
                # [M] emit each lens's pick directly (positions the lenses
                # agree on collapse to one candidate); candidate ranking is
                # objective-terms only + base-contact tie-break -- lens
                # judgement happens at strata selection, not here
                e_min = min(t[4] for t in bay_best)
                seen_pos: set = set()
                for (_ctl, px, py, oi2, entry, _rn, vec) in bay_best:
                    key = (oi2, px, py, entry)
                    if key in seen_pos:
                        continue
                    seen_pos.add(key)
                    exit_m = entry + proc
                    tardy = max(0.0, exit_m - due)
                    new_loads = list(st.loads)
                    new_loads[bay_id] += workload
                    d_hard = w1 * tardy + w3 * (s_max - prefs[bay_id])
                    if o2_mode in ("gh", "gz"):
                        d_bal = w2 * (_h_obj2(new_loads)
                                      - _h_obj2(st.loads))
                    else:
                        d_bal = _o2w() * (_obj2_now(new_loads, u)
                                          - _obj2_now(st.loads, u))
                    d_rank = (d_hard + d_bal - mu * vec[0]
                              + wait_w * (entry - e_min))
                    if (anchor is not None
                            and anchor.get(bi, bay_id) != bay_id):
                        d_rank += anchor_w
                    cands.append((d_rank, d_hard, vec, bay_id, oi2,
                                  px, py, entry))
                continue
            # per distinct entry time keep the best (highest contact)
            # placement; emit up to n_entry_opts earliest entries as
            # separate candidates so the beam can trade time vs packing.
            _sc_n0 = len(cands)
            _sc_cov = (_ogc_core is not None and not merge and not fast
                       and not _EPSHADOW and (_CPP or _CPPCHK))
            _cq2 = None
            if _sc_cov:
                try:
                    if _CPPFAIL:
                        raise RuntimeError("CPP_FAIL")
                    _bbn = len(bay_best)
                    _avx = anchor.get(bi) if anchor is not None else None
                    _cpp_use[1] += 1
                    _cq2 = _ogc_core.score_bay(
                        np.fromiter((t[0] for t in bay_best),
                                    np.float64, _bbn),
                        np.fromiter((t[1] for t in bay_best),
                                    np.int64, _bbn),
                        np.fromiter((t[2] for t in bay_best),
                                    np.int64, _bbn),
                        np.fromiter((t[3] for t in bay_best),
                                    np.int64, _bbn),
                        np.fromiter((t[4] for t in bay_best),
                                    np.int64, _bbn),
                        np.fromiter((t[5] for t in bay_best),
                                    np.float64, _bbn),
                        int(n_entry_opts), int(bool(ori_div)),
                        int(pos_diverse is True
                            or (pos_diverse == "early" and progress < 0.4)),
                        np.asarray(st.loads, np.float64),
                        np.asarray(u, np.float64), float(W_rem),
                        int(bay_id), float(workload),
                        int(o2_mode in ("gh", "gz")), float(_o2w()),
                        float(w1), float(w2), float(w3),
                        float(s_max - prefs[bay_id]), float(due),
                        int(proc), float(mu), float(wait_w), float(pr_w),
                        (np.asarray(R_pr, np.float64)
                         if R_pr is not None else np.zeros(1)),
                        int(R_pr is not None),
                        (1 if _avx is not None else 0),
                        (anchor_w if (_avx is not None
                                      and _avx != bay_id) else 0.0),
                        -1, 0.0, -1, 0.0)
                except Exception:
                    _cq2 = None
            if _cq2 is not None and _CPP and not _CPPCHK:
                _dr2, _dh2, _ct2, _oi2q, _px2q, _py2q, _en2q = _cq2
                for _i2 in range(len(_dr2)):
                    cands.append((float(_dr2[_i2]), float(_dh2[_i2]),
                                  float(_ct2[_i2]), bay_id,
                                  int(_oi2q[_i2]), int(_px2q[_i2]),
                                  int(_py2q[_i2]), int(_en2q[_i2])))
                continue
            per_entry: dict[int, list] = {}
            for t in bay_best:
                per_entry.setdefault(t[4], []).append(t)
            e_list = sorted(per_entry)[:n_entry_opts]
            e_min = e_list[0]
            c_min = max(t[0] for t in per_entry[e_min])
            ring_n = per_entry[e_min][0][5]
            emit = []
            for e in e_list:
                lst = per_entry[e]
                best_contact = max(lst, key=lambda t: t[0])
                emit.append(best_contact)
                if ori_div:
                    # D1: keep the runner-up ORIENTATION alive as its own
                    # candidate -- collapsing 8 orientations to one
                    # representative was starving the beam's branching
                    others = [t for t in lst if t[3] != best_contact[3]]
                    if others:
                        emit.append(max(others, key=lambda t: t[0]))
                if pos_diverse is True or (pos_diverse == "early"
                                           and progress < 0.4):
                    best_bl = min(lst, key=lambda t: (t[2], t[1]))  # (py, px)
                    if best_bl[1:3] != best_contact[1:3]:
                        emit.append(best_bl)
                elif _EPSHADOW and e == e_min:
                    # [EP1] shadow gate: build the bottom-left alternative
                    # but do NOT emit it -- only compute the child-rank it
                    # WOULD have had, so P(made the beam) can be measured
                    # with zero behaviour change.
                    _bl = min(lst, key=lambda t: (t[2], t[1]))
                    if _bl[1:3] != best_contact[1:3]:
                        _c2, _px2, _py2, _oi2, _e2b, _rn2 = _bl
                        _td2 = max(0.0, _e2b + proc - due)
                        _nl2 = list(st.loads)
                        _nl2[bay_id] += workload
                        _dh2 = w1 * _td2 + w3 * (s_max - prefs[bay_id])
                        _h2 = (w2 * _h_obj2(_nl2)
                               if o2_mode in ("gh", "gz")
                               else _o2w() * _obj2_now(_nl2, u))
                        _sval = (st.cum_hard + _dh2 + _h2
                                 - mu * (st.cum_contact + _c2)
                                 - pr_w * st.cum_pr)
                        _ep_step.append((_sval,
                                         occ_cells / max(1, blocked[0].size),
                                         progress))
            for contact, px, py, oi, entry, _rn in emit:
                if entry > e_min and not (c_min < 0.5 * ring_n
                                          and contact > c_min + 0.25 * ring_n):
                    # only offer waiting when the earliest spot is genuinely
                    # poor AND the later spot is substantially better
                    continue
                exit_t = entry + proc
                tardy = max(0.0, exit_t - due)
                new_loads = list(st.loads)
                new_loads[bay_id] += workload
                d_hard = w1 * tardy + w3 * (s_max - prefs[bay_id])
                if o2_mode in ("gh", "gz"):
                    d_bal = w2 * (_h_obj2(new_loads) - _h_obj2(st.loads))
                else:
                    d_bal = _o2w() * (_obj2_now(new_loads, u)
                                      - _obj2_now(st.loads, u))
                d_rank = (d_hard + d_bal - mu * contact
                          + wait_w * (entry - e_min))
                if R_pr is not None:  # [F3] exit near future release mass
                    d_rank -= pr_w * R_pr[min(exit_t, len(R_pr) - 1)]
                if anchor is not None and anchor.get(bi, bay_id) != bay_id:
                    d_rank += anchor_w  # T4: soft pull toward the incumbent
                cands.append((d_rank, d_hard, contact, bay_id, oi,
                              px, py, entry))
            if _CPPCHK and _cq2 is not None:
                _sl = cands[_sc_n0:]
                _dr2, _dh2, _ct2, _oi2q, _px2q, _py2q, _en2q = _cq2
                _cpp_stat[0] += 1
                if not (len(_sl) == len(_dr2) and all(
                        _sl[_i2][0] == _dr2[_i2]
                        and _sl[_i2][1] == _dh2[_i2]
                        and _sl[_i2][2] == _ct2[_i2]
                        and _sl[_i2][4] == _oi2q[_i2]
                        and _sl[_i2][5] == _px2q[_i2]
                        and _sl[_i2][6] == _py2q[_i2]
                        and _sl[_i2][7] == _en2q[_i2]
                        for _i2 in range(len(_sl)))):
                    _cpp_stat[1] += 1
                    raise AssertionError(
                        f"CPPSC mismatch bay={bay_id} "
                        f"n={len(_sl)}/{len(_dr2)}")

        cands.sort(key=lambda c: c[0])
        if R_pr is not None and cands:  # [F3] discrimination diagnostics
            _rs = [R_pr[min(c[7] + proc, len(R_pr) - 1)] for c in cands]
            pr_stat[0] += 1
            if max(_rs) > min(_rs):
                pr_stat[1] += 1
        # late-game candidate cut: placements become near-forced moves, so
        # spend the branching budget early where it changes the future
        # [CG-CAP] late-cap arms: 2 (default) / 4 / 0 = unlocked
        cap = cand_per_state if progress < 0.7 else \
            (_CGCAP if _CGCAP > 0 else cand_per_state)
        top = cands[:cap]
        if _CGLOG and len(cands) > cap:  # [CG1] candidate-cut boundary
            _a, _b = cands[cap - 1], cands[cap]
            _nt = sum(1 for c in cands[cap:]
                      if abs(c[1] - _a[1]) < 1e-9)
            _cg_add(_cg_c, progress, _b[0] - _a[0], _b[1] - _a[1],
                    mu * (_a[2] - _b[2]), _nt)
        # obj3 guard: ALWAYS include the best candidate of EVERY bay that is
        # tied at the maximum preference (pref-tied bays), so the beam never
        # loses the zero-penalty option.
        seen_bays = {c[3] for c in top}
        _g_add = 0
        # [CG-BAY A1] OGC_CGFIX=1: scan from cap, not cand_per_state --
        # with the late cap=2 the old scan skipped indices 2..cps-1 and the
        # guard NEVER fired (measured: prefmax bay lost in 18-41% of late
        # cut events on 38/40) -- the stated invariant was broken.
        _g_from = cap if _CGFIX else cand_per_state
        for c in cands[_g_from:]:
            if prefs[c[3]] == s_max and c[3] not in seen_bays:
                top.append(c)
                seen_bays.add(c[3])
                _g_add += 1
        if _CGBAY2 and progress >= 0.7:
            # [CG-BAY A2] late bay-exhaustive cut: keep the best candidate
            # of EVERY bay (non-pref included) so the late-game bay choice
            # is not structurally locked to the top-2 ([PX] mechanism).
            for c in cands[cap:]:
                if c[3] not in seen_bays:
                    top.append(c)
                    seen_bays.add(c[3])
        if _CGLOG and len(cands) > cap:  # [CG-BAY] late bay-cut counter
            _all_b = {c[3] for c in cands}
            _top_b = {c[3] for c in top}
            _lost = _all_b - _top_b  # bays fully cut (never pref-max ones)
            k2 = min(9, int(progress * 10))
            e2 = _cg_bay.setdefault(k2, [0, 0, 0, 0, 0, 0])
            e2[0] += 1                    # events
            e2[1] += len(_all_b)          # bays offered
            e2[2] += len(_top_b)          # bays surviving
            e2[3] += _g_add               # guard rescues
            e2[4] += 1 if _lost else 0    # events losing >=1 whole bay
            e2[5] += sum(1 for b3 in _lost if prefs[b3] == s_max)
            #             ^ pref-MAX bays lost = guard gap (scan starts at
            #               cand_per_state, skipping indices cap..cps-1)
        return top

    # ---- beam loop -----------------------------------------------------------
    beam = [State(n_bays)]
    if merge:
        beam[0].cum_ct = [0.0] * N_LENS
    lens_named = [0] * N_LENS  # [M] OBS: nominations per lens over the run
    area_total = float(sum(bay_areas))
    B = beam_init if beam_init is not None else \
        auto_beam_width(n_blocks, area_total, timelimit)
    if verbose:
        print(f"  [beam] B={B} (auto={beam_init is None}) "
              f"n_blocks={n_blocks} area={area_total:.0f}", flush=True)
    emergency = False
    n_expanded = 0
    n_children_total = 0  # D5 KPI: candidate states evaluated this run
    n_cuts_total = 0      # OBS: children removed by incumbent pruning
    div_samples: list[float] = []  # D4: unique parents / beam size per step
    canon_samples: list[float] = []  # D4: unique physical states / children
    tcache: dict = {}  # translated neighbour polygons (TIGHT exact verify)
    # D8->D5: cross-STATE blocked-grid cache.  Sibling states share every
    # bay except the one that received the previous block, so their
    # (block, bay, entry) grids are identical -- keyed by the bay's placed
    # sequence hash.  Grids are read-only after build, safe to share.
    grid_cache: dict = {}
    if _S3:  # [S3 v19.5] fresh signature index per solve_beam (rung-local,
        _s3_index.clear()  # same lifetime as the grid_cache it aliases into)
    if _MEMOSHADOW:  # [MEMO0] fresh shadow store per solve_beam (rung)
        _memo_seen.clear()
        _memo_stat[0] = _memo_stat[1] = 0
    if _MEMO:  # [MEMO1] rung-lifetime verdict cache (same life as tcache)
        _memo_cache.clear()
    grid_hits = [0, 0, 0]  # hits, misses, eviction events [GC]
    t_loop = time.time()  # geometry precompute excluded from cost estimate
    recent_costs: list[float] = []  # per-(state,block) cost, last few blocks
    t_prev_block = t_loop
    # [KC0] measurement-only: accumulate EVERY per-(state,block) cost so the
    # run-wide measured cost can be compared against auto_beam_width's
    # PREDICTED est_state_cost.  Logging only -- no behaviour change.
    _kc_sum = 0.0
    _kc_n = 0

    mean_proc = max(1.0, sum(bd["processing_time"]
                             for bd in blocks_data) / n_blocks)
    _suffix_W = [0.0] * (n_blocks + 1)
    for _i in range(n_blocks - 1, -1, -1):
        _suffix_W[_i] = _suffix_W[_i + 1] + blocks_data[order[_i]]["workload"]

    # T1 (D3): free admissible Z3 lower bound for the incumbent pruning --
    # each remaining block pays at least its best FITTING bay's preference
    # penalty (usually 0; positive when the preferred bay is too small).
    # State-independent, so it never touches the rank order.
    _minpen = [0.0] * n_blocks
    for _i in range(n_blocks):
        _prefs = blocks_data[_i]["bay_preferences"]
        _smax = max(_prefs)
        _best = None
        for _j in range(n_bays):
            for _g in geos[_i]:
                if (_g.bbox[2] - _g.bbox[0] <= bay_W[_j] + 1e-9
                        and _g.bbox[3] - _g.bbox[1] <= bay_H[_j] + 1e-9):
                    _p = _smax - _prefs[_j]
                    if _best is None or _p < _best:
                        _best = _p
                    break
            if _best == 0:
                break
        _minpen[_i] = float(_best) if _best is not None else 0.0
    _suffix_pen = [0.0] * (n_blocks + 1)
    for _i in range(n_blocks - 1, -1, -1):
        _suffix_pen[_i] = _suffix_pen[_i + 1] + _minpen[order[_i]]

    # [CG1] cut-boundary decomposition (OGC_CGLOG=1, print-only): at both
    # cut points record whether the boundary gap comes from the objective
    # (d_hard / cum_hard) or from the contact proxy.  buckets by progress
    # decile: [n, hard_tie_events, sum_R_proxy, sum_n_tie]
    _cg_c: dict = {}
    _cg_b: dict = {}
    _cg_bay: dict = {}  # [CG-BAY] late candidate-cut bay coverage
    _ep_hit_prog: dict = {}  # [EP1] shadow hit buckets by progress decile
    _ep_hit_rho: dict = {}   # [EP1] ... by bay-occupancy decile
    _ep_step: list = []      # shadow candidates collected this step

    def _cg_add(bucket, prog, gap, gap_hard, gap_ct, n_tie):
        k = min(9, int(prog * 10))
        e = bucket.setdefault(k, [0, 0, 0.0, 0])
        e[0] += 1
        if abs(gap_hard) < 1e-9:
            e[1] += 1
        e[2] += (gap_ct / gap) if gap > 1e-12 else 1.0
        e[3] += n_tie

    for rank_i, bi in enumerate(order):
        progress = rank_i / max(1, n_blocks - 1)
        if _EPSHADOW:
            _ep_step = []  # fresh shadow pool for this step
        # [F4] elite transplant: rungs sharing this ORDER place identical
        # block sets at every depth, so a mid-run state from the previous
        # rung is a legal state of THIS beam.  Snapshots export the top-m
        # at the quartile depths; immigrants ride along as EXTRA slots
        # (zero width loss) with objective-units-only rank (cum_contact
        # zeroed: their contact trajectory belongs to another lens -- the
        # bounded compromise) and lens_mask bit 3 marking the ancestry so
        # the final best proves or disproves crossbreeding.
        if snap_out is not None and rank_i in _snap_depths and beam:
            snap_out[rank_i] = [s.clone() for s in beam[:snap_m]]
        # lane cost bound (structural, not tuned): the immigrant lane may
        # never exceed HALF the native width -- at B=2 rungs a 3-state
        # lane is a 2.5x per-step cost that time-starves the very rungs
        # the leftover ladder lives on (measured: prob_13's B=2 winning
        # chain fell back to its pre-ladder value, +5.0%)
        if immigrants and rank_i in immigrants and not emergency \
                and not merge and B >= 2 * snap_m:
            for im in immigrants[rank_i]:
                ch = im.clone()
                ch.cum_contact = 0.0
                ch.cum_pr = 0.0
                ch.lens_mask |= 8
                beam.append(ch)
        W_rem = _suffix_W[rank_i + 1]  # remaining after the current block
        if o2_mode == "gz" or _HZ:  # [HZ v19.8] rank term needs D2 demands
            rem = order[rank_i + 1:]
            step_demands.clear()
            if rem:
                dems = sorted((blocks_data[j]["due_date"],
                               _shape_area(blocks_data[j])
                               * blocks_data[j]["processing_time"])
                              for j in rem)
                cum = 0.0
                for due_k, dem_k in dems:
                    cum += dem_k
                    step_demands.append((due_k, cum))
                step_meta[0] = min(blocks_data[j]["release_time"]
                                   for j in rem)
                step_meta[1] = max(1.0, sum(_shape_area(blocks_data[j])
                                            for j in rem) / len(rem))
        # schedule="decay": wide early (many reachable futures), narrow late
        # schedule="flat" : constant width for congested instances
        if schedule == "decay":
            B_now = max(B_MIN, int(round(B * (n_blocks - rank_i) / n_blocks)))
        elif schedule == "decay2":
            # steeper: superlinear narrowing -- even more effort up front
            frac_left = (n_blocks - rank_i) / n_blocks
            B_now = max(B_MIN, int(round(B * frac_left ** 1.5)))
        elif schedule == "hybrid":
            # wide early WITHOUT starving the endgame: decay curve with a
            # floor at half the initial width
            frac_left = (n_blocks - rank_i) / n_blocks
            B_now = max(B_MIN, int(round(B * 0.5)),
                        int(round(B * frac_left ** 1.5)))
        else:
            B_now = B
        bd = blocks_data[bi]
        proc = int(bd["processing_time"])
        n_par = len(beam)  # parent states expanded this step
        n_expanded += n_par
        children = []
        seen_sigs = set()
        for st in beam:
            for (d_rank, d_hard, contact, bay_id, oi, px, py, entry) \
                    in gen_candidates(st, bi, fast=emergency):
                sig = hash((st.sig, bay_id, px, py, oi, entry))
                if sig in seen_sigs:
                    continue  # identical continuation of an identical state
                seen_sigs.add(sig)
                ch = st.clone()
                exit_t = entry + proc
                ch.placed[bay_id].append((bi, oi, px, py, entry, exit_t))
                ch.seq_sigs[bay_id] = hash((ch.seq_sigs[bay_id],
                                            bi, oi, px, py, entry, exit_t))
                ch.loads[bay_id] += bd["workload"]
                ch.cum_hard += d_hard
                if merge and isinstance(contact, tuple):
                    # [M] record the chosen position's contact as seen by
                    # EVERY lens -- each lens's rank stays trajectory-
                    # consistent even over mixed-ancestry states
                    ch.cum_ct = [a + b for a, b in zip(ch.cum_ct, contact)]
                    ch.cum_contact += contact[0]
                else:
                    ch.cum_contact += contact
                if R_pr is not None:  # [F3] exit-release alignment
                    ch.cum_pr += R_pr[min(exit_t, len(R_pr) - 1)]
                ch.psig = st.sig
                ch.sig = sig
                # order-independent state identity: XOR of placement hashes
                # (same physical assignment reached via different orders ->
                # same canon; md's permutation symmetry)
                ch.canon = st.canon ^ hash((bi, bay_id, oi, px, py, entry))
                ch.assignments[bi] = {
                    "block_id": bi, "bay_id": bay_id, "x": px, "y": py,
                    "orient_idx": oi, "entry_time": entry, "exit_time": exit_t}
                children.append(ch)

        if not children:
            # safety: place into an empty-bay window.  Must pick a (bay,
            # orientation) whose footprint actually FITS the bay -- the
            # preferred bay may be too small for this block.
            for st in beam:
                bay_id, oi_fit = -1, 0
                for cand_bay in sorted(range(n_bays),
                                       key=lambda j: -bd["bay_preferences"][j]):
                    for oi in range(len(bd["shape"])):
                        g = geos[bi][oi]
                        if (g.bbox[2] - g.bbox[0] <= bay_W[cand_bay] + 1e-9
                                and g.bbox[3] - g.bbox[1]
                                <= bay_H[cand_bay] + 1e-9):
                            bay_id, oi_fit = cand_bay, oi
                            break
                    if bay_id >= 0:
                        break
                geo = geos[bi][oi_fit]
                entry = max([e for (_, _, _, _, _, e) in st.placed[bay_id]]
                            + [int(bd["release_time"])])
                # exact polygon bounds (TIGHT masks under-cover the bbox)
                px = math.ceil(-geo.bbox[0] - 1e-9)
                py = math.ceil(-geo.bbox[1] - 1e-9)
                st.placed[bay_id].append((bi, oi_fit, px, py,
                                          entry, entry + proc))
                st.seq_sigs[bay_id] = hash((st.seq_sigs[bay_id], bi, oi_fit,
                                            px, py, entry, entry + proc))
                st.loads[bay_id] += bd["workload"]
                st.assignments[bi] = {
                    "block_id": bi, "bay_id": bay_id, "x": px, "y": py,
                    "orient_idx": oi_fit, "entry_time": entry,
                    "exit_time": entry + proc}
            children = beam

        # D3: prune states that PROVABLY cannot beat the incumbent.
        # T1 consistency fix: the incumbent is a floor(obj2)-based value
        # while the waterfill h is pre-floor, so h is discounted by the
        # floor slack 1.0 (the old form over-pruned by up to w2 at floor
        # boundaries -- it could cut the optimal subtree).  The lost cut
        # strength is recovered by the free admissible Z3 bound: remaining
        # blocks pay at least their best fitting bay's preference penalty.
        if incumbent != float("inf") and children:
            if T1_OFF:  # pre-fix form (A/B baseline only)
                kept = [ch for ch in children
                        if ch.cum_hard + w2 * _h_obj2(ch.loads)
                        < incumbent - 1e-9]
            else:
                z3_lb = w3 * _suffix_pen[rank_i + 1]
                kept = [ch for ch in children
                        if ch.cum_hard + w2 * (_h_obj2(ch.loads) - 1.0)
                        + z3_lb < incumbent - 1e-9]
            if kept:
                n_cuts_total += len(children) - len(kept)
                children = kept

        n_children_total += len(children)
        if merge and not emergency and children and \
                children[0].cum_ct is not None:
            # [M] strata selection: objective-rank base order, canonical
            # dedup, then each lens nominates its top-B/L by its own view
            # (rank_l = objective terms - mu*cum_ct[l]); duplicate
            # nominations cost no quota; leftovers fill by pure objective
            # rank under the per-parent cap.  Crossbreeding is automatic:
            # a state that survived on lens A's quota is expanded by ALL
            # lenses next step.
            def _obj_r(ch2):
                if o2_mode in ("gh", "gz"):
                    return ch2.cum_hard + w2 * _h_obj2(ch2.loads)
                return ch2.cum_hard + _o2w() * _obj2_now(ch2.loads, u)
            base_r = {id(ch2): _obj_r(ch2) for ch2 in children}
            children.sort(key=lambda ch2: base_r[id(ch2)])
            seen_canon = set()
            uniq = []
            for ch in children:
                if ch.canon in seen_canon:
                    continue
                seen_canon.add(ch.canon)
                uniq.append(ch)
            canon_samples.append(len(uniq) / max(1, len(children)))
            children = uniq
            for pos, ch in enumerate(children):
                ch.hist.append(pos)
            quota_l = max(1, B_now // N_LENS)
            picked = []
            picked_ids = set()
            for l in range(N_LENS):
                took = 0
                for ch in sorted(children,
                                 key=lambda c2: base_r[id(c2)]
                                 - mu * c2.cum_ct[l]):
                    if took >= quota_l:
                        break
                    ch.lens_mask |= (1 << l)
                    if id(ch) in picked_ids:
                        continue  # duplicate nomination -> no quota spent
                    picked.append(ch)
                    picked_ids.add(id(ch))
                    lens_named[l] += 1
                    took += 1
            quota = max(2, (B_now + 1) // 2)
            per_parent = {}
            for ch in picked:
                per_parent[ch.psig] = per_parent.get(ch.psig, 0) + 1
            for ch in children:  # open slots: pure objective order
                if len(picked) >= B_now:
                    break
                if id(ch) in picked_ids:
                    continue
                pp = per_parent.get(ch.psig, 0)
                if pp >= quota:
                    continue
                per_parent[ch.psig] = pp + 1
                picked.append(ch)
                picked_ids.add(id(ch))
            if len(picked) < B_now:
                for ch in children:
                    if len(picked) >= B_now:
                        break
                    if id(ch) not in picked_ids:
                        picked.append(ch)
                        picked_ids.add(id(ch))
            beam = picked
            div_samples.append(len(per_parent) / max(1, len(beam)))
        else:
            children.sort(key=rank)
            # D4: canonical dedup -- identical PHYSICAL states reached via
            # different orders are true duplicates; keep the best-ranked
            seen_canon = set()
            uniq = []
            for ch in children:
                if ch.canon in seen_canon:
                    continue
                seen_canon.add(ch.canon)
                uniq.append(ch)
            canon_samples.append(len(uniq) / max(1, len(children)))
            children = uniq
            for pos, ch in enumerate(children):
                ch.hist.append(pos)  # rank among ALL children at this step
            if _EPSHADOW and _ep_step:  # [EP1] would the shadow have made it?
                _rl = [rank(c2) for c2 in children]  # ascending (sorted)
                for _sval, _rho2, _pg in _ep_step:
                    _pos2 = sum(1 for r2 in _rl if r2 < _sval)
                    _hit = 1 if _pos2 < B_now else 0
                    for _bkk, _ax in ((_ep_hit_prog, _pg),
                                      (_ep_hit_rho, _rho2)):
                        _kk = min(9, int(_ax * 10))
                        _ee = _bkk.setdefault(_kk, [0, 0])
                        _ee[0] += 1
                        _ee[1] += _hit
            if _CGLOG and len(children) > B_now:  # [CG1] beam-cut boundary
                _a2, _b2 = children[B_now - 1], children[B_now]
                _nt2 = sum(1 for c2 in children[B_now:]
                           if abs(c2.cum_hard - _a2.cum_hard) < 1e-9)
                _cg_add(_cg_b, progress, rank(_b2) - rank(_a2),
                        _b2.cum_hard - _a2.cum_hard,
                        mu * (_a2.cum_contact - _b2.cum_contact), _nt2)
            # [F4] two-lane selection: immigrant-lineage states ride a
            # SEPARATE m-slot lane so the native line keeps its full B --
            # v1 (ordinary states after entry, per the doc) measured the
            # displacement failure the doc's "full-B 그대로" was meant to
            # exclude: rung-1-descended immigrants outranked the esh-lens
            # natives mid-run and destroyed prob_30's winning trajectory
            # (+25%).  The lanes only interact through canonical dedup
            # and the final min().
            if immigrants:
                imm_lane = [ch for ch in children if ch.lens_mask & 8]
                children = [ch for ch in children
                            if not (ch.lens_mask & 8)]
            else:
                imm_lane = []
            # D4: per-parent quota -- without it the top-K often collapses
            # to children of ONE parent, effective width drops to ~1
            quota = max(2, (B_now + 1) // 2)
            picked = []
            picked_ids = set()
            per_parent = {}
            for ch in children:
                if len(picked) >= B_now:
                    break
                pp = per_parent.get(ch.psig, 0)
                if pp >= quota:
                    continue
                per_parent[ch.psig] = pp + 1
                picked.append(ch)
                picked_ids.add(id(ch))
            if len(picked) < B_now:  # fill leftovers ignoring quota
                for ch in children:
                    if len(picked) >= B_now:
                        break
                    if id(ch) not in picked_ids:
                        picked.append(ch)
                        picked_ids.add(id(ch))
            beam = picked + imm_lane[:snap_m]  # [F4] extra lane, no
            #                                    native displacement
            div_samples.append(len(per_parent) / max(1, len(beam)))

        # The B schedule is fixed by block index (deterministic trajectory).
        # Emergency: PREDICTIVE timelimit guard.  From the measured average
        # cost per (state, block) expansion, estimate what finishing the
        # remaining blocks single-file (B=1) would cost, and bail out early
        # enough that the fallback itself still fits inside the limit.
        now = time.time()
        elapsed = now - t0
        # per-(state,block) cost of THIS block (recent costs predict the
        # tail far better than the run average: late congested blocks scan
        # many more entry candidates than early ones)
        _kc_c = (now - t_prev_block) / max(1, n_par)
        recent_costs.append(_kc_c)
        if len(recent_costs) > 8:
            recent_costs.pop(0)
        _kc_sum += _kc_c   # [KC0] run-wide measured cost (logging only)
        _kc_n += 1
        t_prev_block = now
        if not emergency and rank_i >= 5:
            per_state = sum(recent_costs) / len(recent_costs)
            n_left = n_blocks - rank_i - 1
            # the emergency fast path (preferred bay only, no contact conv)
            # costs ~1/6 of a normal expansion; fire as late as possible
            fallback_cost = n_left * per_state * 0.35 + 1.0
            if elapsed + fallback_cost > timelimit and len(beam) > 1:
                emergency = True
        if emergency:
            beam = beam[:1]
        if verbose and (rank_i + 1) % max(1, n_blocks // 5) == 0:
            print(f"  [beam] {rank_i+1}/{n_blocks}  B_now={B_now}  "
                  f"best_rank={rank(beam[0]):.0f}  {elapsed:.1f}s", flush=True)
        # [PR] step 0 (gated OBS, behavior-preserving): the scalar rank
        # subtracts mu*cum_contact, but cum_contact accumulates per
        # placement (grows ~n) while the objective terms grow at their own
        # rate -- if the contact term's share of |rank| drifts up with
        # depth, PR1-a's dilution defect is real.  Log the components of
        # the whole beam at depth quartiles.
        if _os.environ.get("OGC_PRDRIFT") == "1" and \
                rank_i in (n_blocks // 4, n_blocks // 2,
                           (3 * n_blocks) // 4, n_blocks - 1):
            _hs = []
            _ct = []
            for _s in beam:
                _h = (w2 * _h_obj2(_s.loads) if o2_mode in ("gh", "gz")
                      else _o2w() * _obj2_now(_s.loads, u))
                _hs.append(_s.cum_hard + _h)
                _ct.append(mu * _s.cum_contact)
            _obj_m = sum(_hs) / len(_hs)
            _ct_m = sum(_ct) / len(_ct)
            print(f"PRDRIFT depth={rank_i + 1}/{n_blocks} B={len(beam)}"
                  f" obj_mean={_obj_m:.1f} muct_mean={_ct_m:.1f}"
                  f" ratio={_ct_m / max(1e-9, abs(_obj_m)):.4f}"
                  f" ct_raw={sum(s.cum_contact for s in beam)/len(beam):.1f}",
                  flush=True)

    # FINAL selection by the TRUE objective (not the heuristic rank):
    # cum_hard is exact (w1*sum tardy + w3*sum prefpen); obj2 uses the same
    # floor(max pairwise imbalance) as check_feasibility.  The contact bonus
    # is a search guide only and must not decide the final answer.
    def true_obj(st: State) -> float:
        return st.cum_hard + w2 * math.floor(_obj2_now(st.loads, u))

    best = min(beam, key=true_obj)
    best_was_rank0 = best is beam[0]
    solution = {"operations": _build_operations(list(best.assignments.values()))}
    hist = best.hist
    n_h = len(hist)
    _el = max(1e-9, time.time() - t0)
    # [KC0] predicted vs measured per-(state,block) cost.  auto_beam_width
    # sizes B from the PREDICTED constant, so B never responds to how fast
    # the kernel actually is -- this line quantifies that gap.  Logging only.
    if _os.environ.get("OGC_KC") == "1" and _kc_n:
        _kc_pred = (K_COST * (S * S / 4.0) * (1.5 if TIGHT else 1.0)
                    * (0.6 if NATIVE else 1.0)
                    * area_total * (0.5 + n_blocks / 200.0))
        _kc_meas = _kc_sum / _kc_n
        print(f"KC pred={_kc_pred:.4e} meas={_kc_meas:.4e}"
              f" ratio={_kc_meas / max(1e-12, _kc_pred):.3f}"
              f" B={B} n_blocks={n_blocks} area={area_total:.0f}"
              f" emerg={1 if emergency else 0} el={_el:.1f}", flush=True)
    if _CGLOG:  # [CG1] summary: one line per (cut, progress decile)
        for _nm, _bk in (("cand", _cg_c), ("beam", _cg_b)):
            for _k in sorted(_bk):
                _n, _t, _rp, _ns = _bk[_k]
                print(f"CG cut={_nm} prog={_k / 10:.1f} n={_n}"
                      f" P_tie={_t / _n:.3f} R_proxy={_rp / _n:.3f}"
                      f" n_tie_avg={_ns / _n:.1f}", flush=True)
    if _MEMOSHADOW and _memo_stat[0]:
        print(f"MEMO calls={_memo_stat[0]} hit="
              f"{_memo_stat[1] / _memo_stat[0]:.3f}"
              f" keys={len(_memo_seen)}", flush=True)
    if _EPSHADOW:
        for _nm2, _bk2 in (("prog", _ep_hit_prog), ("rho", _ep_hit_rho)):
            for _k in sorted(_bk2):
                _n2, _h2s = _bk2[_k]
                print(f"EPS axis={_nm2} bin={_k / 10:.1f} n={_n2}"
                      f" P_hit={_h2s / _n2:.3f}", flush=True)
    if _CGLOG:
        for _k in sorted(_cg_bay):
            _n, _off, _sur, _g, _le, _pm = _cg_bay[_k]
            print(f"CGBAY prog={_k / 10:.1f} n={_n}"
                  f" bays_off={_off / _n:.2f} bays_kept={_sur / _n:.2f}"
                  f" guard={_g / _n:.2f} lost_ev={_le / _n:.3f}"
                  f" prefmax_lost={_pm / _n:.3f}", flush=True)
    stats = {"elapsed": round(_el, 1), "B": B,
             "emergency": emergency,
             # D5 KPI baseline: candidate evaluations the budget bought
             "n_expanded": n_expanded,
             "n_children": n_children_total,
             "children_per_sec": round(n_children_total / _el, 1),
             "cuts": n_cuts_total,
             "grid_hit_rate": round(grid_hits[0]
                                    / max(1, grid_hits[0] + grid_hits[1]), 3),
             "grid_miss": grid_hits[1], "grid_evict": grid_hits[2],
             "canon_unique": round(sum(canon_samples)
                                   / max(1, len(canon_samples)), 3),
             "diversity": round(sum(div_samples) / max(1, len(div_samples)), 3),
             "final_pick_was_rank0": best_was_rank0,
             "lineage_nonzero_steps": sum(1 for h in hist if h > 0),
             "lineage_max_pos": max(hist) if hist else 0,
             "lineage_early_nonzero": sum(1 for h in hist[:n_h // 3] if h > 0),
             "lineage_early_max": max(hist[:n_h // 3], default=0),
             # [M] crossbreeding evidence: which lens quotas the winner's
             # ancestry passed (>=2 bits set = merged beam is doing what
             # sequential rungs cannot), plus nominations per lens
             "lens_mask": best.lens_mask,
             "lens_named": list(lens_named),
             # [F3] P-R diagnostics: of the expansions scored, how many had
             # ANY cross-candidate variance in the release-histogram lookup
             "pr_stat": list(pr_stat)}
    return solution, stats


def rebalance(prob_info: dict, solution: dict, max_flip: int = 2,
              rounds: int = 4, verbose: bool = False) -> dict:
    """Post-pass: fix obj2 by moving a few blocks across bays.

    The beam cannot see the FINAL load split while placing blocks (obj2 is a
    global end-state quantity), so a cheap arithmetic enumeration of k-block
    bay flips is run on the finished solution; each improving flip set is
    committed only if the flipped blocks re-insert feasibly at their original
    entry/exit times (verified with the same conservative raster machinery).
    """
    import itertools
    blocks = prob_info["blocks"]
    bays = prob_info["bays"]
    w = prob_info["weights"]
    w2, w3 = w["w2"], w["w3"]
    n_bays = len(bays)
    areas = [b["width"] * b["height"] for b in bays]
    avg = sum(areas) / n_bays
    u = [avg / a for a in areas]

    asg: dict[int, dict] = {}
    for t, ops in solution["operations"].items():
        for o in ops:
            if o["type"] == "ENTRY":
                asg[o["block_id"]] = dict(o)
                asg[o["block_id"]]["entry"] = int(t)
    for t, ops in solution["operations"].items():
        for o in ops:
            if o["type"] == "EXIT":
                asg[o["block_id"]]["exit"] = int(t)

    geo_cache: dict[tuple, OrientGeo] = {}
    _rb_tcache: dict = {}
    KMAX = max(len(sh["layers"]) for bd in blocks for sh in bd["shape"])

    def geo_of(bi, oi):
        if (bi, oi) not in geo_cache:
            geo_cache[(bi, oi)] = orient_geo(blocks[bi]["shape"][oi]["layers"])
        return geo_cache[(bi, oi)]

    def try_insert(bi, tgt):
        """Feasible (oi, x, y) for block bi in bay tgt at its current
        entry/exit times, or None."""
        a = asg[bi]
        entry, exit_t = a["entry"], a["exit"]
        W, H = bays[tgt]["width"], bays[tgt]["height"]
        GW, GH = W * S, H * S
        placed = [(k, v["orient_idx"], v["x"], v["y"], v["entry"], v["exit"])
                  for k, v in asg.items() if v["bay_id"] == tgt and k != bi]
        blocked = None
        for oi in range(len(blocks[bi]["shape"])):
            geo = geo_of(bi, oi)
            if blocked is None:
                blocked = [np.zeros((GH, GW), dtype=np.float32)
                           for _ in range(KMAX)]
                for (pb, po, px, py, pa, pe) in placed:
                    if not ((pa < exit_t and pe > entry) or pe == exit_t):
                        continue
                    pg = geo_of(pb, po)
                    gx, gy = px * S + pg.cx0, py * S + pg.cy0
                    need_ge = (pa < entry < pe or (pa == entry and pb < bi)
                               or pa < exit_t < pe
                               or (pe == exit_t and pb > bi))
                    need_le = ((pa == entry and pb > bi)
                               or (pe == exit_t and pa < exit_t and pb < bi)
                               or entry < pa < exit_t or entry < pe < exit_t)
                    sl = (slice(gy, gy + pg.ny), slice(gx, gx + pg.nx))
                    if need_ge:
                        for k in range(min(KMAX, pg.K)):
                            blocked[k][sl] += pg.masks_ge[k]
                    if need_le:
                        for k in range(KMAX):
                            blocked[k][sl] += pg.masks_le[min(k, pg.K - 1)]
                    if not (need_ge or need_le):
                        for k in range(min(KMAX, pg.K)):
                            blocked[k][sl] += pg.masks[k]
            tot, ok = None, True
            for k in range(geo.K):
                c = _conv_count(blocked[k], geo.masks_f32[k])
                if c is None:
                    ok = False
                    break
                tot = c if tot is None else tot + c
            if not ok:
                continue
            px_lo = max(math.ceil(-geo.cx0 / S),
                        math.ceil(-geo.bbox[0] - 1e-9))
            px_hi = min((GW - geo.nx - geo.cx0) // S,
                        math.floor(W - geo.bbox[2] + 1e-9))
            py_lo = max(math.ceil(-geo.cy0 / S),
                        math.ceil(-geo.bbox[1] - 1e-9))
            py_hi = min((GH - geo.ny - geo.cy0) // S,
                        math.floor(H - geo.bbox[3] + 1e-9))
            if px_lo > px_hi or py_lo > py_hi:
                continue
            gys = np.arange(py_lo, py_hi + 1) * S + geo.cy0
            gxs = np.arange(px_lo, px_hi + 1) * S + geo.cx0
            feas = tot[np.ix_(gys, gxs)] < 0.5
            if feas.any():
                iy, ix = np.nonzero(feas)
                for jj in range(min(len(ix), VERIFY_TRIES if TIGHT else 1)):
                    px = int(ix[jj] + px_lo)
                    py = int(iy[jj] + py_lo)
                    if not TIGHT or _exact_ok(
                            geo, px, py, bi, entry, exit_t,
                            placed, None, _rb_tcache, W, H,
                            geos_lookup=geo_of):
                        return oi, px, py
        return None

    def obj23(loads, pen):
        if n_bays < 2:
            imb = 0.0
        else:
            imb = max(abs(u[i] * loads[i] - u[j] * loads[j])
                      for i in range(n_bays) for j in range(n_bays) if i != j)
        return w2 * math.floor(imb) + w3 * pen

    for _ in range(rounds):
        loads = [0.0] * n_bays
        pen0 = 0.0
        for bi, a in asg.items():
            loads[a["bay_id"]] += blocks[bi]["workload"]
            p = blocks[bi]["bay_preferences"]
            pen0 += max(p) - p[a["bay_id"]]
        base = obj23(loads, pen0)

        flips = []  # (gain, [(bi, tgt)])
        items = list(asg.items())
        singles = []
        for bi, a in items:
            p = blocks[bi]["bay_preferences"]
            for tgt in range(n_bays):
                if tgt == a["bay_id"]:
                    continue
                singles.append((bi, a["bay_id"], tgt,
                                blocks[bi]["workload"],
                                p[a["bay_id"]] - p[tgt]))
        for combo in itertools.chain(
                itertools.combinations(singles, 1),
                itertools.combinations(singles, 2) if max_flip >= 2 else []):
            bis = [c[0] for c in combo]
            if len(set(bis)) < len(bis):
                continue
            nl = list(loads)
            dpen = 0.0
            for (bi, src, tgt, wl, dp) in combo:
                nl[src] -= wl
                nl[tgt] += wl
                dpen += dp
            gain = base - obj23(nl, pen0 + dpen)
            if gain > 0:
                flips.append((gain, [(c[0], c[2]) for c in combo]))
        flips.sort(reverse=True)

        committed = False
        for gain, moves in flips[:50]:
            spots = {}
            ok = True
            for bi, tgt in moves:
                spot = try_insert(bi, tgt)
                if spot is None:
                    ok = False
                    break
                spots[bi] = (tgt, spot)
            if not ok:
                continue
            for bi, (tgt, (oi, x, y)) in spots.items():
                asg[bi].update(bay_id=tgt, orient_idx=oi, x=x, y=y)
            if verbose:
                print(f"  [rebalance] gain={gain:.0f} moves={moves}",
                      flush=True)
            committed = True
            break
        if not committed:
            break

    out = [{"block_id": bi, "bay_id": a["bay_id"], "x": a["x"], "y": a["y"],
            "orient_idx": a["orient_idx"], "entry_time": a["entry"],
            "exit_time": a["exit"]} for bi, a in asg.items()]
    return {"operations": _build_operations(out)}


def time_repair(prob_info: dict, solution: dict, timelimit: float = 30.0,
                verbose: bool = False, mode: str = "single",
                lns_k: int = 8, disagree=None,
                max_iters: int = 0) -> dict:
    """Ruin-and-recreate on the TIME axis: pull the most-tardy blocks one at
    a time and re-insert them at the earliest feasible entry over ALL bays x
    orientations x entry candidates, everything else fixed.  A block can
    always return to its old slot, so each commit strictly improves
    w1*tardy + w3*pref + w2*obj2 -- monotone and always feasible."""
    t0 = time.time()
    blocks = prob_info["blocks"]
    bays = prob_info["bays"]
    w = prob_info["weights"]
    w1, w2, w3 = w["w1"], w["w2"], w["w3"]
    n_bays = len(bays)
    areas = [b["width"] * b["height"] for b in bays]
    avg = sum(areas) / n_bays
    u = [avg / a for a in areas]

    asg: dict[int, dict] = {}
    for t, ops in solution["operations"].items():
        for o in ops:
            if o["type"] == "ENTRY":
                asg[o["block_id"]] = dict(o)
                asg[o["block_id"]]["entry"] = int(t)
    for t, ops in solution["operations"].items():
        for o in ops:
            if o["type"] == "EXIT":
                asg[o["block_id"]]["exit"] = int(t)

    def geo_of(bi, oi):
        return orient_geo(blocks[bi]["shape"][oi]["layers"])

    tcache: dict = {}
    KMAX = max(len(sh["layers"]) for bd in blocks for sh in bd["shape"])
    jitter_rng = None  # set by the LNS loop for repair diversity

    def search_place(bi):
        """Best (bay, oi, px, py, entry) for bi with all others fixed."""
        bd = blocks[bi]
        r_time = int(bd["release_time"])
        proc = int(bd["processing_time"])
        due = bd["due_date"]
        prefs = bd["bay_preferences"]
        s_max = max(prefs)
        cur_bay = asg[bi]["bay_id"]
        loads = [0.0] * n_bays
        for bj, a in asg.items():
            if bj != bi:
                loads[a["bay_id"]] += blocks[bj]["workload"]
        best = None  # (score, bay, oi, px, py, entry)
        for bay_id in range(n_bays):
            W, H = bays[bay_id]["width"], bays[bay_id]["height"]
            GW, GH = W * S, H * S
            placed = [(k, v["orient_idx"], v["x"], v["y"],
                       v["entry"], v["exit"])
                      for k, v in asg.items()
                      if v["bay_id"] == bay_id and k != bi]
            entries = sorted({r_time} | {e for (_, _, _, _, _, e) in placed
                                         if e > r_time})
            nl = list(loads)
            nl[bay_id] += bd["workload"]
            d_o2 = w2 * _obj2_now(nl, u)
            found_entry = None
            for entry in entries:
                exit_t = entry + proc
                # prune: even a perfect slot here cannot beat current best
                cand_score = (w1 * max(0.0, exit_t - due)
                              + w3 * (s_max - prefs[bay_id]) + d_o2)
                if best is not None and cand_score >= best[0]:
                    break
                blocked = [np.zeros((GH, GW), dtype=np.float32)
                           for _ in range(KMAX)]
                for (pb, po, ppx, ppy, pa, pe) in placed:
                    if not ((pa < exit_t and pe > entry) or pe == exit_t):
                        continue
                    pg = geo_of(pb, po)
                    gx, gy = ppx * S + pg.cx0, ppy * S + pg.cy0
                    need_ge = (pa < entry < pe or (pa == entry and pb < bi)
                               or pa < exit_t < pe
                               or (pe == exit_t and pb > bi))
                    need_le = ((pa == entry and pb > bi)
                               or (pe == exit_t and pa < exit_t and pb < bi)
                               or entry < pa < exit_t or entry < pe < exit_t)
                    sl = (slice(gy, gy + pg.ny), slice(gx, gx + pg.nx))
                    if need_ge:
                        for k in range(min(KMAX, pg.K)):
                            blocked[k][sl] += pg.masks_ge[k]
                    if need_le:
                        for k in range(KMAX):
                            blocked[k][sl] += pg.masks_le[min(k, pg.K - 1)]
                    if not (need_ge or need_le):
                        for k in range(min(KMAX, pg.K)):
                            blocked[k][sl] += pg.masks[k]
                ok_any = False
                for oi in range(len(bd["shape"])):
                    geo = geo_of(bi, oi)
                    tot, fit = None, True
                    for k in range(geo.K):
                        c = _conv_count(blocked[k], geo.masks_f32[k])
                        if c is None:
                            fit = False
                            break
                        tot = c if tot is None else tot + c
                    if not fit:
                        continue
                    px_lo = max(math.ceil(-geo.cx0 / S),
                                math.ceil(-geo.bbox[0] - 1e-9))
                    px_hi = min((GW - geo.nx - geo.cx0) // S,
                                math.floor(W - geo.bbox[2] + 1e-9))
                    py_lo = max(math.ceil(-geo.cy0 / S),
                                math.ceil(-geo.bbox[1] - 1e-9))
                    py_hi = min((GH - geo.ny - geo.cy0) // S,
                                math.floor(H - geo.bbox[3] + 1e-9))
                    if px_lo > px_hi or py_lo > py_hi:
                        continue
                    gys = np.arange(py_lo, py_hi + 1) * S + geo.cy0
                    gxs = np.arange(px_lo, px_hi + 1) * S + geo.cx0
                    feas = tot[np.ix_(gys, gxs)] < 0.5
                    if not feas.any():
                        continue
                    iy, ix = np.nonzero(feas)
                    order_bl = np.argsort(iy * 100000 + ix)
                    # jitter (LNS repair diversity): a deterministic repair
                    # rebuilds the SAME solution after every ruin -- when a
                    # jitter rng is supplied, pick randomly among the first
                    # few verified positions instead of always the best
                    passed = []
                    want = 3 if jitter_rng is not None else 1
                    for jj in order_bl[:max(VERIFY_TRIES if TIGHT else 1,
                                            want * 3)]:
                        px = int(ix[jj] + px_lo)
                        py = int(iy[jj] + py_lo)
                        if not TIGHT or _exact_ok(
                                geo, px, py, bi, entry, exit_t, placed,
                                None, tcache, W, H, geos_lookup=geo_of):
                            passed.append((px, py))
                            if len(passed) >= want:
                                break
                    if passed:
                        px, py = (jitter_rng.choice(passed)
                                  if jitter_rng is not None else passed[0])
                        best = (cand_score, bay_id, oi, px, py, entry)
                        ok_any = True
                        break
                if ok_any:
                    break  # earliest feasible entry found for this bay
        return best

    # ---- exact arithmetic objective of the current asg ----------------------
    def _total_obj():
        loads = [0.0] * n_bays
        tardy = pen = 0.0
        for bj, a in asg.items():
            loads[a["bay_id"]] += blocks[bj]["workload"]
            tardy += max(0.0, a["exit"] - blocks[bj]["due_date"])
            p = blocks[bj]["bay_preferences"]
            pen += max(p) - p[a["bay_id"]]
        imb = max(abs(u[i] * loads[i] - u[j] * loads[j])
                  for i in range(n_bays) for j in range(n_bays)
                  if i != j) if n_bays >= 2 else 0.0
        return w1 * tardy + w2 * math.floor(imb) + w3 * pen

    # ---- D7: batch-ruin LNS with deterministic adaptive operator choice -----
    if mode == "lns":
        import random as _random
        rng = _random.Random(20260711)  # fixed seed: runs stay reproducible
        jitter_rng = rng  # repair picks among top verified positions
        # full objective coverage (md D7): Z1 (tardy_cluster), Z2
        # (bay_heavy), Z3 (pref_k), packing (spatial), diversify (random_k)
        ops = ["tardy_cluster", "bay_heavy", "random_k", "pref_k", "spatial"]
        # T2 (D6xD7): blocks the four parallel lenses assigned to DIFFERENT
        # bays -- the portfolio's own uncertainty marks the ruin targets.
        # ALNS weights starve the operator automatically if the
        # disagreement turns out to be noise.
        dis_pool = [b for b in (disagree or []) if True]
        if dis_pool:
            ops.append("disagree")
        wts = {o: 1.0 for o in ops}
        op_stat = {o: [0, 0, 0, 0.0]
                   for o in ops}  # picked, accepted, improved, gain
        # [B] B5-1 OBS (behavior-preserving): per-thirds operator pick
        # counts + weight snapshots, to empirically test B0's claim that
        # late-game weights degenerate to uniform (== max selection entropy)
        _seg_on = _os.environ.get("OGC_ALNSSEG") == "1"
        _seg_pick = [{o: 0 for o in ops} for _ in range(3)]
        _seg_imp = [{o: 0 for o in ops} for _ in range(3)]
        cur = _total_obj()
        best_snap = {bj: dict(a) for bj, a in asg.items()}
        best_obj_l = cur
        it = n_acc = 0
        # T5-ext: with max_iters > 0 the LNS is an ITERATION-budgeted pass
        # (deterministic trajectory when the wall cap does not bind); the
        # wall clock stays as a pure safety ceiling
        while ((max_iters <= 0 or it < max_iters)
               and time.time() - t0 < timelimit):
            it += 1
            # weighted deterministic-pseudo-random operator pick (ALNS)
            tot = sum(wts.values())
            r = rng.random() * tot
            op = ops[-1]
            for o in ops:
                r -= wts[o]
                if r <= 0:
                    op = o
                    break
            if _seg_on and max_iters > 0:
                _sg = min(2, (it - 1) * 3 // max_iters)
                _seg_pick[_sg][op] += 1
            K = lns_k
            victims: list[int] = []
            if op == "tardy_cluster":
                tl = sorted(((max(0.0, a["exit"] - blocks[bj]["due_date"]),
                              bj) for bj, a in asg.items()), reverse=True)
                if tl and tl[0][0] > 0:
                    b0 = tl[rng.randrange(min(5, len(tl)))][1]
                    a0 = asg[b0]
                    pool = [bj for bj, a in asg.items()
                            if a["bay_id"] == a0["bay_id"] and bj != b0
                            and a["entry"] < a0["exit"] + 5
                            and a["exit"] > a0["entry"] - 5]
                    rng.shuffle(pool)
                    victims = [b0] + pool[:K - 1]
            elif op == "bay_heavy":
                loads = [0.0] * n_bays
                for bj, a in asg.items():
                    loads[a["bay_id"]] += blocks[bj]["workload"]
                heavy = max(range(n_bays), key=lambda j: u[j] * loads[j])
                pool = [bj for bj, a in asg.items()
                        if a["bay_id"] == heavy]
                rng.shuffle(pool)
                victims = pool[:K]
            elif op == "disagree":
                pool = [bj for bj in dis_pool if bj in asg]
                rng.shuffle(pool)
                victims = pool[:K]
            elif op == "pref_k":
                # Z3: blocks currently paying a preference penalty
                pool = [bj for bj, a in asg.items()
                        if max(blocks[bj]["bay_preferences"])
                        - blocks[bj]["bay_preferences"][a["bay_id"]] > 0]
                rng.shuffle(pool)
                victims = pool[:K]
            elif op == "spatial":
                # packing: a spatial cluster around a (biased tardy) seed
                tl = sorted(((max(0.0, a["exit"] - blocks[bj]["due_date"]),
                              bj) for bj, a in asg.items()), reverse=True)
                b0 = tl[rng.randrange(min(8, len(tl)))][1]
                a0 = asg[b0]
                pool = sorted(
                    (bj for bj, a in asg.items()
                     if a["bay_id"] == a0["bay_id"] and bj != b0),
                    key=lambda bj: (abs(asg[bj]["x"] - a0["x"])
                                    + abs(asg[bj]["y"] - a0["y"])))
                victims = [b0] + pool[:K - 1]
            else:
                pool = list(asg.keys())
                rng.shuffle(pool)
                victims = pool[:K]
            if not victims:
                wts[op] = max(0.2, wts[op] * 0.9)
                continue
            snapshot = {bj: dict(asg[bj]) for bj in victims}
            # ruin: drop the victims, then repair at each block's best
            # placement given everything else fixed.  The REPAIR ORDER is
            # itself diversified (same ruin, different rebuilds).
            for bj in victims:
                del asg[bj]
            r_mode = rng.randrange(3)
            if r_mode == 0:      # EDD, big first
                repair_seq = sorted(victims,
                                    key=lambda x: (blocks[x]["due_date"],
                                                   -blocks[x]["workload"]))
            elif r_mode == 1:    # latest-start-time urgency
                repair_seq = sorted(victims,
                                    key=lambda x: blocks[x]["due_date"]
                                    - blocks[x]["processing_time"])
            else:                # shuffled
                repair_seq = list(victims)
                rng.shuffle(repair_seq)
            ok = True
            for bj in repair_seq:
                asg[bj] = snapshot[bj]  # provisional (search needs an entry)
                best = search_place(bj)
                if best is None:
                    ok = False
                    break
                _, bay_id, oi, px, py, entry = best
                asg[bj].update(bay_id=bay_id, orient_idx=oi, x=px, y=py,
                               entry=entry,
                               exit=entry + int(blocks[bj]["processing_time"]))
            new = _total_obj() if ok else float("inf")
            op_stat[op][0] += 1
            # SA-lite acceptance: small worsenings are accepted with a
            # temperature that cools as the budget runs out (escape flat
            # local optima early, intensify late).  The BEST solution is
            # tracked separately, so acceptance can never worsen the output.
            # T5-ext: iteration-based cooling when iteration-budgeted --
            # the trajectory then depends only on (input, k, max_iters),
            # not on machine speed
            if max_iters > 0:
                frac_left = max(0.0, 1.0 - it / max_iters)
            else:
                frac_left = max(0.0, 1.0 - (time.time() - t0) / timelimit)
            temp = max(1e-9, 0.002 * cur * frac_left)
            accept = ok and (new < cur - 1e-6
                             or rng.random() < math.exp(
                                 min(0.0, (cur - new) / temp)))
            if accept:
                improved_l = new < cur - 1e-6
                cur_prev = cur
                cur = new
                if new < best_obj_l - 1e-6:
                    best_obj_l = new
                    best_snap = {bj: dict(a) for bj, a in asg.items()}
                n_acc += 1
                op_stat[op][1] += 1
                if improved_l:
                    op_stat[op][2] += 1
                    op_stat[op][3] += max(0.0, cur_prev - new)
                    if _seg_on and max_iters > 0:
                        _seg_imp[min(2, (it - 1) * 3 // max_iters)][op] += 1
                wts[op] = min(8.0, wts[op] + (1.0 if improved_l else 0.1))
                if verbose and improved_l:
                    print(f"  [lns] it={it} {op} accepted -> {cur:.0f}",
                          flush=True)
            else:
                for bj in victims:  # rollback
                    asg[bj] = snapshot[bj]
                wts[op] = max(0.2, wts[op] * 0.9)
        if verbose:
            print(f"  [lns] iters={it} accepted={n_acc} wts={wts}",
                  flush=True)
            print(f"  [lns] op_stat (picked/accepted/improved): "
                  f"{op_stat}", flush=True)
        if _os.environ.get("OGC_DEBUG") == "1":
            for o in ops:  # OBS 3: one parse-friendly line per operator
                print(f"ALNS op={o} try={op_stat[o][0]}"
                      f" acc={op_stat[o][1]} gain={op_stat[o][3]:.0f}"
                      f" w_final={wts[o]:.2f}", flush=True)
        if _seg_on:  # [B] B5-1: per-thirds pick entropy (uniform => max)
            import math as _m
            n_ops = len(ops)
            emax = _m.log(n_ops) if n_ops > 1 else 1.0
            for _s in range(3):
                tot = sum(_seg_pick[_s].values())
                if tot == 0:
                    continue
                ent = -sum((c / tot) * _m.log(c / tot)
                           for c in _seg_pick[_s].values() if c > 0)
                dist = {o: _seg_pick[_s][o] for o in ops}
                imp = {o: _seg_imp[_s][o] for o in ops}
                print(f"ALNSSEG seg={_s} n={tot} ent={ent / emax:.3f}"
                      f" pick={dist} imp={imp}", flush=True)
        out = [{"block_id": bi, "bay_id": a["bay_id"], "x": a["x"],
                "y": a["y"], "orient_idx": a["orient_idx"],
                "entry_time": a["entry"], "exit_time": a["exit"]}
               for bi, a in best_snap.items()]
        return {"operations": _build_operations(out)}

    rounds = 0
    n_moved = 0
    while time.time() - t0 < timelimit:
        tardy_list = sorted(
            ((max(0.0, a["exit"] - blocks[bi]["due_date"]), bi)
             for bi, a in asg.items()), reverse=True)
        moved = False
        for tardy, bi in tardy_list:
            if tardy <= 0 or time.time() - t0 > timelimit:
                break
            a = asg[bi]
            bd = blocks[bi]
            prefs = bd["bay_preferences"]
            loads = [0.0] * n_bays
            for bj, aa in asg.items():
                if bj != bi:
                    loads[aa["bay_id"]] += blocks[bj]["workload"]
            nl = list(loads)
            nl[a["bay_id"]] += bd["workload"]
            cur_score = (w1 * tardy + w3 * (max(prefs) - prefs[a["bay_id"]])
                         + w2 * _obj2_now(nl, u))
            best = search_place(bi)
            if best is not None and best[0] < cur_score - 1e-6:
                _, bay_id, oi, px, py, entry = best
                asg[bi].update(bay_id=bay_id, orient_idx=oi, x=px, y=py,
                               entry=entry, exit=entry + int(bd["processing_time"]))
                n_moved += 1
                moved = True
                if verbose:
                    print(f"  [time_repair] block {bi} tardy {tardy:.0f} -> "
                          f"entry {entry} bay{bay_id}", flush=True)
        rounds += 1
        if not moved:
            break

    if verbose:
        print(f"  [time_repair] rounds={rounds} moved={n_moved}", flush=True)
    out = [{"block_id": bi, "bay_id": a["bay_id"], "x": a["x"], "y": a["y"],
            "orient_idx": a["orient_idx"], "entry_time": a["entry"],
            "exit_time": a["exit"]} for bi, a in asg.items()]
    return {"operations": _build_operations(out)}


# ---------------------------------------------------------------------------
# [C] compression / justification -- scheduling transplant (v14).
# A pure TIME move never changes geometry: with (x, y, orient) fixed, whether
# blocks i and p geometrically collide is time-INVARIANT -- time only decides
# WHICH collision condition applies (co-resident same-layer, or the j>=k
# crane sweep in either direction).  So all pairwise geometry is computed
# ONCE (exact shapely, mirroring the judge) and every candidate time move
# afterwards is an O(bay blocks) boolean lookup, no geometry at all.

def _time_pattern(entry, exit_t, bi, pa, pe, pb):
    """Mirror of _exact_ok's temporal case analysis for mover `bi` against
    a fixed resident (pa, pe, pb) -- INCLUDING the same-time block-id tie
    rules.  None = no interaction; else (need_ge, need_le)."""
    if not ((pa < exit_t and pe > entry) or pe == exit_t):
        return None
    need_ge = (pa < entry < pe or (pa == entry and pb < bi)
               or pa < exit_t < pe or (pe == exit_t and pb > bi))
    need_le = ((pa == entry and pb > bi)
               or (pe == exit_t and pa < exit_t and pb < bi)
               or entry < pa < exit_t or entry < pe < exit_t)
    return need_ge, need_le


def _pair_flags(polys_a, polys_b):
    """(co, ge, le) for the ordered pair (a, b): co = same-layer overlap,
    ge = exists k, j>=k with layer_k(a) hitting layer_j(b) (a moving past
    resident b), le = the j<=k counterpart (== ge of the swapped pair)."""
    co = ge = le = False
    for k, pk in enumerate(polys_a):
        bk = pk.bounds
        for j, pj in enumerate(polys_b):
            bj = pj.bounds
            if (bk[2] <= bj[0] or bj[2] <= bk[0]
                    or bk[3] <= bj[1] or bj[3] <= bk[1]):
                continue
            g = pk.intersection(pj)
            if g.is_empty or g.area <= 0.0:
                continue
            if j == k:
                co = True
            if j >= k:
                ge = True
            if j <= k:
                le = True
    return co, ge, le


class JustifyCtx:
    """[C1] pairwise time-invariant collision matrix over ONE solution.

    Search-side only -- utils.check_feasibility remains the judge (D0).
    Shared by justify_time and the mirror unit test."""

    def __init__(self, prob_info, solution, flag_cache=None):
        self.blocks = prob_info["blocks"]
        asg = {}
        for t, ops in solution["operations"].items():
            for o in ops:
                if o["type"] == "ENTRY":
                    a = dict(o)
                    a["entry"] = int(t)
                    asg[o["block_id"]] = a
        for t, ops in solution["operations"].items():
            for o in ops:
                if o["type"] == "EXIT":
                    asg[o["block_id"]]["exit"] = int(t)
        self.asg = asg
        # [C-A A2] flags & bay_blocks are SPACE-determined (bay,x,y,orient)
        # and time-INVARIANT, so cache them on the space signature; a hit
        # skips the whole O(blocks^2) shapely matrix.  asg (times) is always
        # rebuilt above -- justify's own time moves never invalidate.
        space_sig = tuple(sorted(
            (b, a["bay_id"], a["x"], a["y"], a["orient_idx"])
            for b, a in asg.items()))
        if flag_cache is not None and flag_cache.get("sig") == space_sig:
            self.bay_blocks = flag_cache["bay_blocks"]
            self.flags = flag_cache["flags"]
            return
        self.bay_blocks: dict[int, list[int]] = {}
        for b, a in asg.items():
            self.bay_blocks.setdefault(a["bay_id"], []).append(b)
        geo_cache: dict[tuple, list] = {}

        def polys_of(bi, oi, x, y):
            key = (bi, oi, x, y)
            v = geo_cache.get(key)
            if v is None:
                g = orient_geo(self.blocks[bi]["shape"][oi]["layers"])
                v = [_shp_translate(p, x, y) for p in g.polys]
                geo_cache[key] = v
            return v

        self.flags: dict[tuple, tuple] = {}
        for bay, blist in self.bay_blocks.items():
            for i2 in range(len(blist)):
                a = blist[i2]
                aa = asg[a]
                pa_ = polys_of(a, aa["orient_idx"], aa["x"], aa["y"])
                for j2 in range(i2 + 1, len(blist)):
                    b = blist[j2]
                    ab = asg[b]
                    pb_ = polys_of(b, ab["orient_idx"], ab["x"], ab["y"])
                    self.flags[(a, b)] = _pair_flags(pa_, pb_)
        if flag_cache is not None:
            flag_cache["sig"] = space_sig
            flag_cache["bay_blocks"] = self.bay_blocks
            flag_cache["flags"] = self.flags

    def _fl(self, m, p):
        """Oriented (mover, resident) flags (co, GE, LE)."""
        v = self.flags.get((m, p))
        if v is not None:
            return v
        co, ge, le = self.flags[(p, m)]
        return co, le, ge

    def move_ok(self, m, e_new):
        """Is moving block m to entry e_new (same bay/pos/orient) legal
        against every resident of its bay?  Geometry checks: zero."""
        am = self.asg[m]
        x_new = e_new + (am["exit"] - am["entry"])
        for p in self.bay_blocks[am["bay_id"]]:
            if p == m:
                continue
            ap = self.asg[p]
            pat = _time_pattern(e_new, x_new, m, ap["entry"], ap["exit"], p)
            if pat is None:
                continue
            ge, le = pat
            co, GE, LE = self._fl(m, p)
            if ge and le:
                if GE or LE:
                    return False
            elif ge:
                if GE:
                    return False
            elif le:
                if LE:
                    return False
            elif co:
                return False
        return True

    def commit(self, m, e_new):
        a = self.asg[m]
        proc = a["exit"] - a["entry"]
        a["entry"], a["exit"] = e_new, e_new + proc

    def solution(self):
        out = [{"block_id": b, "bay_id": a["bay_id"], "x": a["x"],
                "y": a["y"], "orient_idx": a["orient_idx"],
                "entry_time": a["entry"], "exit_time": a["exit"]}
               for b, a in self.asg.items()]
        return {"operations": _build_operations(out)}


def justify_time(prob_info, solution, direction="fbi", max_rounds=4,
                 scan="bp", ctx=None, flag_cache=None):
    """[C2/C3] right-justification (objective-INVARIANT: exit<=due kept,
    z2 is workload-based, z3 assignment-based) and FBI (right -> left
    round trips; the left pass may pull LATE blocks earlier, reducing Z1
    directly, and is monotone-safe: an earlier exit never raises T).
    Returns (solution, moved_count).

    [C-A A1] scan="bp" (default) probes only the DISCRETE breakpoints where
    move_ok's verdict can change (a resident's entry/exit, offset by proc,
    plus +-1 for the ==-tie boundaries) instead of every tick -- O(blocks^2)
    not O(slack x blocks).  scan="full" keeps the exhaustive tick scan for
    the behavior-preserving equivalence test (must match bp exactly).
    flag_cache (a dict) enables [C-A A2] reuse: the space-signature keyed
    shapely matrix is skipped when the incoming solution's space is
    unchanged since the last call."""
    if ctx is None:
        ctx = JustifyCtx(prob_info, solution, flag_cache=flag_cache)
    blocks = prob_info["blocks"]
    total = 0
    rounds_log = []
    _prev_rsig = None

    def _cands_right(m, lo_excl, hi_incl, proc):
        # legality flips only near residents' entry/exit; first feasible in
        # DESCENDING order == the max feasible e (== the full scan's pick)
        if scan == "full":
            return range(hi_incl, lo_excl, -1)
        cs = {hi_incl}
        bay = ctx.asg[m]["bay_id"]
        for p in ctx.bay_blocks[bay]:
            if p == m:
                continue
            ap = ctx.asg[p]
            for t0 in (ap["entry"], ap["exit"]):
                cs.update((t0, t0 - proc, t0 + 1, t0 - 1,
                           t0 - proc + 1, t0 - proc - 1))
        return sorted((e for e in cs if lo_excl < e <= hi_incl),
                      reverse=True)

    def _cands_left(m, lo_incl, hi_excl, proc):
        if scan == "full":
            return range(lo_incl, hi_excl)
        cs = {lo_incl}
        bay = ctx.asg[m]["bay_id"]
        for p in ctx.bay_blocks[bay]:
            if p == m:
                continue
            ap = ctx.asg[p]
            for t0 in (ap["entry"], ap["exit"]):
                cs.update((t0, t0 - proc, t0 + 1, t0 - 1,
                           t0 - proc + 1, t0 - proc - 1))
        return sorted(e for e in cs if lo_incl <= e < hi_excl)

    for _r in range(max_rounds):
        n_moved = 0
        if direction in ("right", "fbi"):
            for m in sorted(ctx.asg, key=lambda b: -ctx.asg[b]["exit"]):
                a = ctx.asg[m]
                proc = a["exit"] - a["entry"]
                due = blocks[m]["due_date"]
                if a["exit"] > due:
                    continue  # late block: any right move raises Z1
                for e in _cands_right(m, a["entry"], due - proc, proc):
                    if ctx.move_ok(m, e):
                        ctx.commit(m, e)
                        n_moved += 1
                        break
        if direction in ("left", "fbi"):
            for m in sorted(ctx.asg, key=lambda b: ctx.asg[b]["entry"]):
                a = ctx.asg[m]
                proc = a["exit"] - a["entry"]
                rel = blocks[m]["release_time"]
                for e in _cands_left(m, rel, a["entry"], proc):
                    if ctx.move_ok(m, e):
                        ctx.commit(m, e)
                        n_moved += 1
                        break
        total += n_moved
        rounds_log.append(n_moved)
        # [C-A A3.3] FBI oscillates rather than reaching moved==0 (right and
        # left passes undo each other), so the moved counter stays positive
        # forever while the ROUND-BOUNDARY configuration is already fixed
        # after round 1 (verified: obj+placement invariant r1..r4 on the
        # representative set).  Break on config stability, not moved==0 --
        # instance-robust, and eliminates the 4x churn (output byte-identical).
        rsig = hash(tuple(sorted((b, a["entry"])
                                 for b, a in ctx.asg.items())))
        if n_moved == 0 or rsig == _prev_rsig:
            break
        _prev_rsig = rsig
    if _os.environ.get("OGC_DEBUG") == "1":
        print(f"JUSTIFY dir={direction} rounds={rounds_log}", flush=True)
    return ctx.solution(), total


PORTFOLIO = (
    # (order_name, rank_mode, pos_diverse, beam_mult, schedule, pos_lam)
    # flat  : constant width -- congested instances need width to the end
    # decay : linear narrowing, 2x initial width -- front-loads the search
    # pos_lam: contact-vs-low-skyline tradeoff in the position score
    # Ordered by priority: large instances run only the first few configs.
    # Two widths of the proven winner come first: quality is chronically
    # B-sensitive and the budget-driven auto width lands on different B per
    # timelimit -- the width pair hedges that.
    ("edd_big", "v0",   False, 1.0, "flat",  0.01),
    ("edd_big", "v0",   False, 1.5, "flat",  0.01),
    ("edd_big", "noL",  False, 1.0, "flat",  0.5),
    ("edd_big", "ramp", True,  1.0, "decay", 0.01),
)

def solve_multi(prob_info: dict, timelimit: float = 300.0,
                configs=PORTFOLIO,
                beam_init: int | None = None, verbose: bool = True):
    """Portfolio multi-start: one beam run per (order, rank, diversity)
    config, best final objective wins."""
    t0 = time.time()
    best = None
    n_blocks = len(prob_info["blocks"])
    area_total = float(sum(b["width"] * b["height"]
                           for b in prob_info["bays"]))
    # size-aware config count: each config must afford a flat beam of >= ~4,
    # otherwise drop lower-priority configs and give survivors more budget
    est_state_cost = (K_COST * (S * S / 4.0) * (1.5 if TIGHT else 1.0)
                      * (0.6 if NATIVE else 1.0)
                      * area_total * (0.5 + n_blocks / 200.0))
    per_needed = 4 * n_blocks * est_state_cost / 0.8
    # reserve part of the budget for the post-passes (time_repair moves the
    # most-tardy blocks to earlier entries -- worth ~15% of the budget on
    # congested instances; a no-op costs nothing when T=0)
    post_reserve = min(45.0, 0.15 * timelimit)
    budget = timelimit - post_reserve
    n_cfg = max(1, min(len(configs), int(budget / max(1e-9, per_needed))))
    configs = configs[:n_cfg]
    per = budget / len(configs)
    for (on, rm, pd, bm, sched, lam) in configs:
        remaining = timelimit - (time.time() - t0)
        if remaining < per * 0.4:
            break
        b_auto = auto_beam_width(n_blocks, area_total, per)
        if sched == "flat":
            b_auto = max(B_MIN, b_auto // 2)  # flat spends B x n, not B x n/2
        elif sched == "hybrid":
            b_auto = max(B_MIN, int(b_auto * 0.85))  # avg width ~0.59 B0
        b = beam_init if beam_init is not None else \
            max(B_MIN, int(b_auto * bm))
        sol, st = solve_beam(prob_info, timelimit=min(per, remaining),
                             beam_init=b, order_name=on,
                             rank_mode=rm, pos_diverse=pd, schedule=sched,
                             pos_lam=lam, verbose=False)
        res = check_feasibility(prob_info, sol)
        obj = res["objective"] if res["feasible"] else float("inf")
        if verbose:
            print(f"  [multi] {on}/{rm}/pd={pd}/{sched}/lam={lam}/B={b} "
                  f"obj={obj} "
                  f"(o1={res['obj1']}, o2={res['obj2']}, o3={res['obj3']}) "
                  f"{st['elapsed']}s", flush=True)
        if best is None or obj < best[0]:
            best = (obj, sol, (on, rm, pd, b, sched, lam), res)

    # leftover-budget reuse: fast instances finish the portfolio early --
    # re-run the winning config with a wider beam on the remaining time
    remaining = timelimit - (time.time() - t0)
    if best is not None and remaining > max(10.0, per * 0.5):
        on, rm, pd, b, sched, lam = best[2]
        b2 = int(b * 1.6)
        sol, st = solve_beam(prob_info, timelimit=remaining * 0.9,
                             beam_init=b2, order_name=on,
                             rank_mode=rm, pos_diverse=pd, schedule=sched,
                             pos_lam=lam, verbose=False)
        res = check_feasibility(prob_info, sol)
        obj = res["objective"] if res["feasible"] else float("inf")
        if verbose:
            print(f"  [multi] RETRY {on}/{rm}/pd={pd}/{sched}/B={b2} "
                  f"obj={obj} {st['elapsed']}s", flush=True)
        if obj < best[0]:
            best = (obj, sol, (on, rm, pd, b2, sched, lam), res)

    # time-repair post-pass: re-insert the most-tardy blocks at earlier
    # feasible entries (monotone; uses whatever budget remains)
    tr_budget = timelimit - (time.time() - t0) - 3.0
    if best is not None and tr_budget > 3.0:
        sol_t = time_repair(prob_info, best[1], timelimit=tr_budget,
                            verbose=verbose)
        res_t = check_feasibility(prob_info, sol_t)
        if res_t["feasible"] and res_t["objective"] < best[0]:
            if verbose:
                print(f"  [multi] TIME_REPAIR {best[0]} -> "
                      f"{res_t['objective']}", flush=True)
            best = (res_t["objective"], sol_t, best[2], res_t)

    # rebalance post-pass: fix the end-state load split the beam cannot see
    sol2 = rebalance(prob_info, best[1], verbose=verbose)
    res2 = check_feasibility(prob_info, sol2)
    if res2["feasible"] and res2["objective"] < best[0]:
        if verbose:
            print(f"  [multi] REBALANCE {best[0]} -> {res2['objective']}",
                  flush=True)
        best = (res2["objective"], sol2, best[2], res2)

    return best[1], {"best_config": best[2], "objective": best[0],
                     "elapsed": round(time.time() - t0, 1)}


if __name__ == "__main__":
    prob_path = sys.argv[1]
    tl = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
    Bi = int(sys.argv[3]) if len(sys.argv) > 3 else None
    with open(prob_path, encoding="utf-8") as f:
        prob = json.load(f)
    sol, stats = solve_beam(prob, timelimit=tl, beam_init=Bi)
    res = check_feasibility(prob, sol)
    print(json.dumps({"feasible": res["feasible"], "stage": res["stage"],
                      "objective": res["objective"], "obj1": res["obj1"],
                      "obj2": res["obj2"], "obj3": res["obj3"], **stats}))
    if not res["feasible"]:
        for v in res["violations"][:8]:
            print("VIOL:", v)









# -*- coding: utf-8 -*-
"""
gridsolver.py -- full-grid candidate solver with pluggable spatial score functions.

Step 1 (candidate generation): for every block (EDD order), enumerate
  ALL bays x ALL orientations x ALL integer (x, y) positions.
Feasibility over the full grid is computed at once per (bay, orientation,
entry-time) via FFT convolution on conservative raster masks (scale S=2),
so a raster-feasible placement is guaranteed polygon-feasible
(entry sweep j>=k, exit sweep j>=k, and same-layer stage-4 co-presence).

Step 2 (selection): among feasible positions the SPATIAL score function
(pluggable, see SCORE_FNS) picks the best position within each
(bay, orient, earliest-entry) candidate; candidates are then compared with
the GLOBAL score  w1*tardiness + w2*d(obj2) + w3*pref_penalty  (+ tiny
spatial tie-break), mirroring the real objective.

The point of this module is to A/B-test spatial score formulas and measure
whether they change the FINAL objective and packing density.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np
import shapely
from shapely.geometry import Polygon as ShapelyPolygon
from scipy.signal import fftconvolve
from scipy.ndimage import binary_dilation

_HERE = os.path.dirname(os.path.abspath(__file__))
_BASELINE = os.path.join(os.path.dirname(_HERE),
                         "baseline-latest-oxXm57Lz (1)", "ogc2026", "baseline")
if _BASELINE not in sys.path:
    sys.path.insert(0, _BASELINE)

from utils import check_feasibility  # noqa: E402  (ground-truth validator)

S = int(os.environ.get("OGC_S", "2"))  # raster cells per grid unit

_GEO_CACHE: dict = {}


def orient_geo(raw_layers) -> "OrientGeo":
    """Memoized OrientGeo -- rasterisation costs ~20s per 250-block instance
    and is identical across portfolio configs, so share it process-wide."""
    key = (S, TIGHT, T_THR, tuple(tuple(tuple(v) for v in layer)
                                  for layer in raw_layers))
    g = _GEO_CACHE.get(key)
    if g is None:
        g = OrientGeo(raw_layers)
        _GEO_CACHE[key] = g
    return g
# TIGHT=1: majority-rule raster (cell occupied iff >= half covered) -- masks
# no longer inflate footprints, but a raster-feasible position is NOT
# guaranteed polygon-feasible; the solver must exact-verify the position it
# commits (see beamsolver).  TIGHT=0: conservative superset raster (any
# intersection blocks the cell) -- feasible-by-construction.
TIGHT = os.environ.get("OGC_TIGHT", "0") == "1"
# TIGHT cell-occupancy threshold: cell blocked iff covered fraction >= T_THR.
# 0.0+ = conservative (any touch), 0.5 = majority, ->1.0 = only fully covered
# cells block.  Higher = tighter packing candidates but higher exact-verify
# rejection cost.  Checker safety is threshold-independent (every committed
# position is polygon-verified).
T_THR = float(os.environ.get("OGC_TIGHT_T", "0.5"))

try:  # numba exact-clipping rasteriser (10-20x faster than shapely here)
    from native_kernel import poly_cell_areas as _fast_raster
except Exception:
    _fast_raster = None


# -----------------------------------------------------------------------------
# Geometry: conservative raster masks per (block, orientation)
# -----------------------------------------------------------------------------

class OrientGeo:
    """Raster masks for one (block, orientation).

    All layers are rasterised on one shared cell frame anchored to the integer
    lattice so that translating the block by integer (px, py) moves the mask
    by exactly (px*S, py*S) cells.

    mask[k]    : bool (ny, nx) -- cells intersected by layer-k polygon
    mask_ge[k] : union of mask[j] for j >= k (crane sweep shadow)
    cx0, cy0   : cell offset of mask origin relative to ref point * S
    """

    __slots__ = ("mv_r", "mv_c", "mv_off",
                 "ring_r", "ring_c", "lring_r", "lring_c", "lring_off",
                 "masks", "masks_ge", "masks_le", "cx0", "cy0", "nx", "ny",
                 "masks_w", "polys_v", "pb",
                 "K", "area0", "top_h", "masks_f32", "cells0", "ring_f32",
                 "rings_u8", "masks_u8", "ring_u8", "polys", "bbox")

    def __init__(self, raw_layers):
        ref_x, ref_y = raw_layers[0][0]
        polys = []
        all_verts_per_layer = []
        for layer in raw_layers:
            verts = [(x - ref_x, y - ref_y) for x, y in layer]
            all_verts_per_layer.append(verts)
            p = ShapelyPolygon(verts)
            if not p.is_valid:
                p = p.buffer(0)
            polys.append(p)
        self.K = len(polys)
        self.area0 = polys[0].area
        self.polys = polys  # anchored exact polygons (for exact verification)
        # [EXN] numba fast-verdict inputs: open exterior rings as float64
        # (n,2) arrays + per-layer base bounds.  Only simple polygons qualify
        # (measured: 0 MultiPolygons / 0 holes across all instances); a
        # buffer(0) repair that yields anything else falls back to the pure
        # shapely path (polys_v = None).
        try:
            if all(p.geom_type == "Polygon" and len(p.interiors) == 0
                   for p in polys):
                self.polys_v = [np.ascontiguousarray(
                    np.asarray(p.exterior.coords[:-1], dtype=np.float64))
                    for p in polys]
                self.pb = [p.bounds for p in polys]
            else:
                self.polys_v = None
                self.pb = None
        except Exception:
            self.polys_v = None
            self.pb = None
        self.bbox = (min(p.bounds[0] for p in polys),
                     min(p.bounds[1] for p in polys),
                     max(p.bounds[2] for p in polys),
                     max(p.bounds[3] for p in polys))  # true polygon bounds

        minx = min(p.bounds[0] for p in polys)
        miny = min(p.bounds[1] for p in polys)
        maxx = max(p.bounds[2] for p in polys)
        maxy = max(p.bounds[3] for p in polys)
        cx0 = math.floor(minx * S - 1e-9)
        cy0 = math.floor(miny * S - 1e-9)
        cx1 = math.ceil(maxx * S + 1e-9)
        cy1 = math.ceil(maxy * S + 1e-9)
        nx, ny = cx1 - cx0, cy1 - cy0

        cell_area = 1.0 / (S * S)
        self.masks = []
        boxes = None
        for p, verts in zip(polys, all_verts_per_layer):
            # exact per-cell coverage: numba clipping (10-20x faster than
            # shapely) for valid simple polygons, shapely fallback otherwise
            areas = None
            if _fast_raster is not None and p.is_valid and \
                    len(p.interiors) == 0:
                vx = np.array([v[0] for v in verts], dtype=np.float64)
                vy = np.array([v[1] for v in verts], dtype=np.float64)
                grid = np.empty((ny, nx), dtype=np.float64)
                _fast_raster(vx, vy, cx0, cy0, nx, ny, S, grid)
                areas = grid.ravel()
            if areas is None:
                if boxes is None:
                    xs = np.arange(cx0, cx1) / S
                    ys = np.arange(cy0, cy1) / S
                    X, Y = np.meshgrid(xs, ys)
                    boxes = shapely.box(X.ravel(), Y.ravel(),
                                        X.ravel() + 1.0 / S,
                                        Y.ravel() + 1.0 / S)
                areas = shapely.area(shapely.intersection(p, boxes))
            if TIGHT:
                m = (areas >= T_THR * cell_area).reshape(ny, nx)
                if not m.any():  # degenerate thin layer: keep conservative
                    m = (areas > 1e-9).reshape(ny, nx)
            else:
                m = (areas > 1e-9).reshape(ny, nx)
            self.masks.append(m)

        # trim to union bounding cells (tight frame -> tight boundary range)
        union = np.zeros((ny, nx), dtype=bool)
        for m in self.masks:
            union |= m
        rows = np.flatnonzero(union.any(axis=1))
        cols = np.flatnonzero(union.any(axis=0))
        r0, r1 = rows[0], rows[-1] + 1
        c0, c1 = cols[0], cols[-1] + 1
        self.masks = [m[r0:r1, c0:c1] for m in self.masks]
        self.cx0 = cx0 + c0
        self.cy0 = cy0 + r0
        self.ny, self.nx = r1 - r0, c1 - c0

        self.masks_ge = []
        acc = np.zeros((self.ny, self.nx), dtype=bool)
        for m in reversed(self.masks):
            acc = acc | m
            self.masks_ge.append(acc.copy())
        self.masks_ge.reverse()

        self.masks_le = []
        acc = np.zeros((self.ny, self.nx), dtype=bool)
        for m in self.masks:
            acc = acc | m
            self.masks_le.append(acc.copy())

        self.masks_f32 = [m.astype(np.float32) for m in self.masks]
        self.cells0 = int(self.masks[0].sum())

        from scipy.ndimage import binary_dilation as _bd
        m_pad = np.zeros((self.ny + 2, self.nx + 2), dtype=bool)
        m_pad[1:-1, 1:-1] = self.masks[0]
        self.ring_f32 = (_bd(m_pad) & ~m_pad).astype(np.float32)
        # E3 (layer accounting): per-layer contact rings -- contact becomes
        # the sum over layers of |ring_k & (layer-k occupancy | wall)|, so
        # profile-nesting placements score their true adjacency
        _rs = []
        for _m in self.masks:
            _mp = np.zeros((self.ny + 2, self.nx + 2), dtype=bool)
            _mp[1:-1, 1:-1] = _m
            _rs.append((_bd(_mp) & ~_mp))
        self.rings_u8 = np.stack(_rs).astype(np.uint8)
        # S1/S3 (speed, behavior-preserving): pre-stacked uint8 mirrors so
        # the native sweep consumes cached grids/masks without per-call
        # stack + astype conversions on every (orientation, entry)
        self.masks_u8 = np.stack(self.masks).astype(np.uint8)
        # [Morton/BP-cache] pre-packed mask words (row -> uint64 words):
        # packing is amortized out of the per-call feasibility sweep.
        _K, _ny, _nx = self.masks_u8.shape
        _Wm = (_nx + 63) // 64
        _mw = np.zeros((_K, _ny, _Wm), np.uint64)
        _one = np.uint64(1)
        for _k in range(_K):
            for _r in range(_ny):
                for _c in range(_nx):
                    if self.masks_u8[_k, _r, _c]:
                        _mw[_k, _r, _c >> 6] |= (_one << np.uint64(_c & 63))
        self.masks_w = _mw
        self.ring_u8 = self.ring_f32.astype(np.uint8)
        # [MC v19.6] sparse ring cell lists: contact counting enumerates
        # ONLY the set perimeter cells instead of scanning the full
        # (ny+2)x(nx+2) box.  Same cells, same boundary rules ->
        # identical counts (MCCHK-audited byte-identical).
        _rr, _rc = np.nonzero(self.ring_u8)
        self.ring_r = _rr.astype(np.int32)
        self.ring_c = _rc.astype(np.int32)
        _lr_r, _lr_c, _off = [], [], [0]
        for _k in range(self.K):
            _r2, _c2 = np.nonzero(self.rings_u8[_k])
            _lr_r.append(_r2)
            _lr_c.append(_c2)
            _off.append(_off[-1] + len(_r2))
        self.lring_r = np.concatenate(_lr_r).astype(np.int32) \
            if _lr_r else np.empty(0, np.int32)
        self.lring_c = np.concatenate(_lr_c).astype(np.int32) \
            if _lr_c else np.empty(0, np.int32)
        self.lring_off = np.array(_off, np.int32)
        # [SV v19.7] sparse mask cell lists (k,r,c order = np.nonzero
        # row-major -> verdict identical to the box scan).  Used by the
        # E_AL sweep only (base/E_CT sparse-verify measured mixed and
        # were rejected -- see SV 판정).
        _mv_r, _mv_c, _mo = [], [], [0]
        for _k in range(self.K):
            _r3, _c3 = np.nonzero(self.masks_u8[_k])
            _mv_r.append(_r3)
            _mv_c.append(_c3)
            _mo.append(_mo[-1] + len(_r3))
        self.mv_r = np.concatenate(_mv_r).astype(np.int32) \
            if _mv_r else np.empty(0, np.int32)
        self.mv_c = np.concatenate(_mv_c).astype(np.int32) \
            if _mv_c else np.empty(0, np.int32)
        self.mv_off = np.array(_mo, np.int32)
        self.top_h = self.ny / S  # bbox height (for top-edge score)


# -----------------------------------------------------------------------------
# Spatial score functions (VECTORIZED over feasible positions; lower = better)
# ctx supplies everything a formula might want.
# -----------------------------------------------------------------------------

def score_topy(pxs, pys, ctx):
    """Baseline-like: minimise the block's top edge (then left)."""
    return (pys + ctx["geo"].top_h) * 1000.0 + pxs


def score_bl(pxs, pys, ctx):
    """Strict bottom-left: lexicographic (y, x)."""
    return pys * 100000.0 + pxs


def score_corner(pxs, pys, ctx):
    """L1 distance from bottom-left corner."""
    return (pxs + pys) * 1000.0 + pys


def score_contact(pxs, pys, ctx):
    """Maximise contact perimeter with walls + blocks present at entry
    (layer-0 union occupancy).  Ties broken bottom-left."""
    contact = ctx["contact_at"](pxs, pys)
    return -contact * 1000.0 + pys * 10.0 + pxs * 0.1


def score_contact_time(pxs, pys, ctx):
    """Contact weighted occupancy where neighbours are weighted by remaining
    co-presence time (prefer nesting against blocks that stay long)."""
    contact = ctx["contact_time_at"](pxs, pys)
    return -contact * 1000.0 + pys * 10.0 + pxs * 0.1


def score_contact_topy(pxs, pys, ctx):
    """Contact first, then prefer a low top edge (compact rows)."""
    contact = ctx["contact_at"](pxs, pys)
    return -contact * 1000.0 + (pys + ctx["geo"].top_h) * 10.0 + pxs * 0.1


def score_contact_wall(pxs, pys, ctx):
    """Contact + extra reward for touching bay walls (corner-seeking)."""
    contact = ctx["contact_at"](pxs, pys)
    geo = ctx["geo"]
    at_wall_x = (pxs * S + geo.cx0 == 0) | \
                (pxs * S + geo.cx0 + geo.nx == ctx["bay_w"] * S)
    at_wall_y = (pys * S + geo.cy0 == 0) | \
                (pys * S + geo.cy0 + geo.ny == ctx["bay_h"] * S)
    wall_bonus = at_wall_x.astype(np.float64) + at_wall_y.astype(np.float64)
    return -(contact + wall_bonus * geo.nx) * 1000.0 + pys * 10.0 + pxs * 0.1


SCORE_FNS = {
    "contact_topy": score_contact_topy,
    "contact_wall": score_contact_wall,
    "topy":         score_topy,
    "bl":           score_bl,
    "corner":       score_corner,
    "contact":      score_contact,
    "contact_time": score_contact_time,
}


# -----------------------------------------------------------------------------
# Solver
# -----------------------------------------------------------------------------

def _conv_count(blocked_f32, mask_f32):
    """out[gy, gx] = sum blocked[gy:gy+ny, gx:gx+nx] * mask  ('valid')."""
    if blocked_f32.shape[0] < mask_f32.shape[0] or \
       blocked_f32.shape[1] < mask_f32.shape[1]:
        return None
    return fftconvolve(blocked_f32, mask_f32[::-1, ::-1], mode="valid")


def solve(prob_info: dict, score_name: str = "topy",
          timelimit: float = 300.0, verbose: bool = True) -> tuple[dict, dict]:
    """Returns (solution_dict, stats_dict)."""
    t0 = time.time()
    score_fn = SCORE_FNS[score_name]

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

    # geometry precompute
    geos: list[list[OrientGeo]] = []
    for bd in blocks_data:
        geos.append([OrientGeo(sh["layers"]) for sh in bd["shape"]])

    # bay state: list of (block_id, oi, px, py, entry, exit)
    placed: list[list[tuple]] = [[] for _ in range(n_bays)]
    bay_loads = [0.0] * n_bays

    order = sorted(range(n_blocks),
                   key=lambda i: (blocks_data[i]["due_date"],
                                  blocks_data[i]["processing_time"]))

    assignments: dict[int, dict] = {}
    stat_feas_positions = []   # feasible position count per commit
    stat_cands_scanned = []    # (bay,orient) combos with a feasible slot

    for rank, bi in enumerate(order):
        bd = blocks_data[bi]
        r_time = int(bd["release_time"])
        due = bd["due_date"]
        proc = int(bd["processing_time"])
        workload = bd["workload"]
        prefs = bd["bay_preferences"]
        s_max = max(prefs)

        best = None  # (global_score, spatial_score, bay, oi, px, py, entry)
        n_feas_combo = 0

        # blocked-grid cache: (bay_id, entry) -> (blocked list, occ0, occ0w)
        blocked_cache: dict[tuple, tuple] = {}

        for bay_id in sorted(range(n_bays), key=lambda j: prefs[j], reverse=True):
            W, H = bay_W[bay_id], bay_H[bay_id]
            GW, GH = W * S, H * S
            entries = sorted({r_time} | {e for (_, _, _, _, a, e)
                                         in placed[bay_id] if e > r_time})

            for oi, geo in enumerate(geos[bi]):
                # integer position bounds from raster frame
                px_lo = math.ceil(-geo.cx0 / S)
                px_hi = (GW - geo.nx - geo.cx0) // S
                py_lo = math.ceil(-geo.cy0 / S)
                py_hi = (GH - geo.ny - geo.cy0) // S
                if px_lo > px_hi or py_lo > py_hi:
                    continue

                found = False
                for entry in entries:
                    exit_t = entry + proc
                    key = (bay_id, entry)
                    if key not in blocked_cache:
                        blocked = [np.zeros((GH, GW), dtype=np.float32)
                                   for _ in range(2)]
                        occ0 = np.zeros((GH, GW), dtype=np.float32)
                        occ0t = np.zeros((GH, GW), dtype=np.float32)
                        for (pb, po, ppx, ppy, pa, pe) in placed[bay_id]:
                            if not ((pa < exit_t and pe > entry) or pe == exit_t):
                                continue
                            pg = geos[pb][po]
                            gx = ppx * S + pg.cx0
                            gy = ppy * S + pg.cy0
                            # Which sweep constraints apply, respecting the
                            # Stage-5 same-time ordering (EXITs before ENTRYs,
                            # each sorted by block_id):
                            #  need_ge : P is resting while OUR crane moves
                            #            -> our layer k avoids P layers >= k
                            #  need_le : P's crane moves while WE are resting
                            #            -> our layer j avoids P layers <= j
                            need_ge = need_le = False
                            if pa < entry < pe or (pa == entry and pb < bi):
                                need_ge = True          # P present at our entry
                            if pa == entry and pb > bi:
                                need_le = True          # P descends after us
                            if pa < exit_t < pe or (pe == exit_t and pb > bi):
                                need_ge = True          # P present at our exit
                            if pe == exit_t and pa < exit_t and pb < bi:
                                need_le = True          # P ascends before us
                            if entry < pa < exit_t or entry < pe < exit_t:
                                need_le = True          # P's event inside our stay
                            sl = (slice(gy, gy + pg.ny), slice(gx, gx + pg.nx))
                            if need_ge:
                                for k in range(min(2, pg.K)):
                                    blocked[k][sl] += pg.masks_ge[k]
                            if need_le:
                                for k in range(2):
                                    blocked[k][sl] += pg.masks_le[min(k, pg.K - 1)]
                            if not (need_ge or need_le):
                                # pure same-layer co-presence (stage-4)
                                for k in range(min(2, pg.K)):
                                    blocked[k][sl] += pg.masks[k]
                            pres_ent = pa <= entry < pe
                            if pres_ent:
                                occ0[sl] += pg.masks[0]
                                occ0t[sl] += pg.masks[0] * float(min(pe, exit_t) - entry)
                        blocked_cache[key] = (blocked, occ0, occ0t)
                    blocked, occ0, occ0t = blocked_cache[key]

                    # feasibility over ALL positions at once
                    tot = None
                    ok = True
                    for k in range(min(2, geo.K)):
                        c = _conv_count(blocked[k], geo.masks[k].astype(np.float32))
                        if c is None:
                            ok = False
                            break
                        tot = c if tot is None else tot[:c.shape[0], :c.shape[1]] + c
                    if not ok:
                        break  # orientation cannot fit this bay at all

                    # sample integer lattice points
                    gys = np.arange(py_lo, py_hi + 1) * S + geo.cy0
                    gxs = np.arange(px_lo, px_hi + 1) * S + geo.cx0
                    sub = tot[np.ix_(gys, gxs)]
                    feas = sub < 0.5
                    if not feas.any():
                        continue

                    iy, ix = np.nonzero(feas)
                    pys = iy + py_lo
                    pxs = ix + px_lo
                    n_pos = len(pxs)

                    # spatial scoring context (lazy contact evaluators)
                    def _make_contact(occ_grid):
                        # pad the mask so 1-cell dilation is not clipped
                        m_pad = np.zeros((geo.ny + 2, geo.nx + 2), dtype=bool)
                        m_pad[1:-1, 1:-1] = geo.masks[0]
                        ring = binary_dilation(m_pad) & ~m_pad
                        ring_f = ring.astype(np.float32)
                        # walls modelled as a 1-cell occupied border
                        ext = np.ones((GH + 2, GW + 2), dtype=np.float32)
                        ext[1:-1, 1:-1] = np.minimum(occ_grid, 1.0) if occ_grid is occ0 else occ_grid
                        conv = fftconvolve(ext, ring_f[::-1, ::-1], mode="valid")
                        # ring origin is grid (gy-1, gx-1) -> ext index (gy, gx)

                        def at(pxa, pya):
                            return conv[pya * S + geo.cy0, pxa * S + geo.cx0]
                        return at

                    ctx = {
                        "geo": geo, "bay_w": W, "bay_h": H,
                        "contact_at": None, "contact_time_at": None,
                    }
                    if score_name.startswith("contact"):
                        ctx["contact_at"] = _make_contact(occ0)
                        ctx["contact_time_at"] = _make_contact(occ0t)

                    sc = score_fn(pxs.astype(np.int64), pys.astype(np.int64), ctx)
                    j = int(np.argmin(sc))
                    px, py, ssc = int(pxs[j]), int(pys[j]), float(sc[j])

                    tardiness = max(0.0, exit_t - due)
                    new_load = bay_loads[bay_id] + workload
                    new_obj2 = max((abs(u[bay_id] * new_load - u[jj] * bay_loads[jj])
                                    for jj in range(n_bays) if jj != bay_id),
                                   default=0.0)
                    gscore = (w1 * tardiness + w2 * new_obj2
                              + w3 * (s_max - prefs[bay_id]))

                    n_feas_combo += 1
                    stat_feas_positions.append(n_pos)
                    if best is None or (gscore, ssc) < (best[0], best[1]):
                        best = (gscore, ssc, bay_id, oi, px, py, entry)
                    found = True
                    break  # earliest feasible entry for this (bay, orient)
                # (entry loop end)
                _ = found

        if best is None:
            # cannot happen if entries include all exits (empty bay eventually),
            # but guard anyway: push past the max exit in preferred bay.
            bay_id = max(range(n_bays), key=lambda j: prefs[j])
            geo = geos[bi][0]
            entry = max([e for (_, _, _, _, _, e) in placed[bay_id]] + [r_time])
            px = math.ceil(-geo.cx0 / S)
            py = math.ceil(-geo.cy0 / S)
            best = (0.0, 0.0, bay_id, 0, px, py, entry)

        _, _, bay_id, oi, px, py, entry = best
        exit_t = entry + proc
        placed[bay_id].append((bi, oi, px, py, entry, exit_t))
        bay_loads[bay_id] += workload
        stat_cands_scanned.append(n_feas_combo)
        assignments[bi] = {"block_id": bi, "bay_id": bay_id, "x": px, "y": py,
                           "orient_idx": oi, "entry_time": entry,
                           "exit_time": exit_t}

        if verbose and (rank + 1) % max(1, n_blocks // 5) == 0:
            print(f"  [{score_name}] {rank+1}/{n_blocks} placed  "
                  f"elapsed={time.time()-t0:.1f}s")
        if time.time() - t0 > timelimit:
            print(f"  [{score_name}] TIMEOUT at {rank+1}/{n_blocks}")
            # place the rest in empty windows (safety)
            for bj in order[rank + 1:]:
                bdj = blocks_data[bj]
                bay_id = max(range(n_bays),
                             key=lambda j: bdj["bay_preferences"][j])
                geo = geos[bj][0]
                entry = max([e for (_, _, _, _, _, e) in placed[bay_id]]
                            + [int(bdj["release_time"])])
                px = math.ceil(-geo.cx0 / S)
                py = math.ceil(-geo.cy0 / S)
                exit_t = entry + int(bdj["processing_time"])
                placed[bay_id].append((bj, 0, px, py, entry, exit_t))
                bay_loads[bay_id] += bdj["workload"]
                assignments[bj] = {"block_id": bj, "bay_id": bay_id,
                                   "x": px, "y": py, "orient_idx": 0,
                                   "entry_time": entry, "exit_time": exit_t}
            break

    solution = {"operations": _build_operations(list(assignments.values()))}

    # ---- packing density: time-averaged layer-0 area utilisation per bay ----
    dens = []
    for j in range(n_bays):
        evts = []
        for (pb, po, _, _, a, e) in placed[j]:
            ar = geos[pb][po].area0
            evts.append((a, ar))
            evts.append((e, -ar))
        if not evts:
            dens.append(0.0)
            continue
        evts.sort()
        t_prev, cur, acc, t_start = evts[0][0], 0.0, 0.0, evts[0][0]
        for t, d in evts:
            acc += cur * (t - t_prev)
            cur += d
            t_prev = t
        span = max(1e-9, t_prev - t_start)
        dens.append(acc / span / bay_areas[j])

    stats = {
        "elapsed": time.time() - t0,
        "avg_feasible_positions": float(np.mean(stat_feas_positions)) if stat_feas_positions else 0.0,
        "avg_feasible_combos": float(np.mean(stat_cands_scanned)) if stat_cands_scanned else 0.0,
        "density_per_bay": [round(d, 4) for d in dens],
        "density_mean": round(float(np.mean(dens)), 4),
    }
    return solution, stats


def _build_operations(assignments: list[dict]) -> dict:
    buckets: dict[int, list[tuple]] = {}
    for a in assignments:
        buckets.setdefault(int(a["exit_time"]), []).append(
            (0, "EXIT", a["block_id"], a["bay_id"], None, None, None))
        buckets.setdefault(int(a["entry_time"]), []).append(
            (1, "ENTRY", a["block_id"], a["bay_id"],
             a["x"], a["y"], a["orient_idx"]))
    operations: dict[str, list[dict]] = {}
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


if __name__ == "__main__":
    prob_path = sys.argv[1]
    score = sys.argv[2] if len(sys.argv) > 2 else "topy"
    with open(prob_path, encoding="utf-8") as f:
        prob = json.load(f)
    sol, stats = solve(prob, score)
    res = check_feasibility(prob, sol)
    print(json.dumps({"score": score, "feasible": res["feasible"],
                      "stage": res["stage"],
                      "objective": res["objective"],
                      "obj1": res["obj1"], "obj2": res["obj2"],
                      "obj3": res["obj3"], **stats}, indent=2))
    if not res["feasible"]:
        for v in res["violations"][:8]:
            print("VIOL:", v)

# -*- coding: utf-8 -*-
"""Fused native feasibility+contact sweep (numba JIT).

Replaces, per (bay, entry, orientation), the scipy fftconvolve calls
(feasibility per layer + contact ring) with ONE compiled loop that
  * visits only integer-lattice positions,
  * early-exits on the first blocked cell,
  * computes the contact score only for feasible positions.

Layer-generic: blocked and mask are stacked (K, H, W) / (K, ny, nx) arrays
(instances have up to 4 layers).  The identical algorithm is provided as
core_engine.cpp for the contest submission (.so via g++).
"""
import os as _os
import numpy as np
from numba import njit

# [BP] gate: route the base-sweep feasibility through the bit-packed kernel
_BITPACK = _os.environ.get("OGC_BITPACK", "0") == "1"
# [MC v19.6] sparse-ring contact counting (default ON; OGC_MC=0 restores
# the box-scan path, OGC_MCCHK=1 runs both and asserts exact equality).
_MC = _os.environ.get("OGC_MC", "1") == "1"
_MCCHK = _os.environ.get("OGC_MCCHK", "0") == "1"
# [SV v19.7] sparse-list E_AL sweep (default ON; OGC_SV=0 restores the
# box-scan sweep_a).  Adopted for the E_AL variant ONLY: base/E_CT
# sparse-verify measured mixed (prob_24 ct +2.0%) and were rejected.
# E_AL line saving 11.7~17.1% (24/26/30/40), no regression sample.
_SV = _os.environ.get("OGC_SV", "1") == "1"
_SVCHK = _os.environ.get("OGC_SVCHK", "0") == "1"  # audit: both, assert ==


@njit(cache=True, fastmath=True)
def _feas_sv(bst, K, gy, gx, mv_r, mv_c, mv_off):
    """[SV] feasibility verify over set mask cells only (k,r,c order
    preserved -> same verdict as the box scan, fewer visits)."""
    for k in range(K):
        for i in range(mv_off[k], mv_off[k + 1]):
            if bst[k, gy + mv_r[i], gx + mv_c[i]]:
                return False
    return True


@njit(cache=True, fastmath=True)
def sweep_a_sv(bst, K,
               Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
               exq, mv_r, mv_c, mv_off, ring_r, ring_c,
               exit_c, W, do_contact,
               out_px, out_py, out_ct):
    """[SV] P-A sweep: sparse mask verify + sparse ring enumeration
    (per-cell aligned-contact logic unchanged, binary threshold)."""
    GH, GW = bst.shape[1], bst.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            if not _feas_sv(bst, K, gy, gx, mv_r, mv_c, mv_off):
                continue
            ct = 0.0
            if do_contact:
                for i in range(ring_r.shape[0]):
                    yy = gy - 1 + ring_r[i]
                    xx = gx - 1 + ring_c[i]
                    if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
                        ct += 1.0  # wall = eternally aligned
                    else:
                        e = exq[yy, xx]
                        if e >= 0:
                            dt = e - exit_c
                            if dt < 0:
                                dt = -dt
                            if dt <= W:
                                ct += 1.0
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True, fastmath=True)
def _ct_rc(occ, gy, gx, GH, GW, ring_r, ring_c):
    """[MC] contact count via sparse ring cell list -- enumerates only the
    set perimeter cells; boundary rules identical to the box scan."""
    ct = 0.0
    for i in range(ring_r.shape[0]):
        yy = gy - 1 + ring_r[i]
        xx = gx - 1 + ring_c[i]
        if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
            ct += 1.0
        elif occ[yy, xx]:
            ct += 1.0
    return ct


@njit(cache=True, fastmath=True)
def _ct_rc_l(occ_st, gy, gx, GH, GW, K, lr_r, lr_c, l_off):
    """[MC] E3 layered contact via per-layer sparse ring lists."""
    ct = 0.0
    for k in range(K):
        for i in range(l_off[k], l_off[k + 1]):
            yy = gy - 1 + lr_r[i]
            xx = gx - 1 + lr_c[i]
            if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
                ct += 1.0  # bay wall exists at every layer
            elif occ_st[k, yy, xx]:
                ct += 1.0
    return ct


@njit(cache=True, fastmath=True)
def sweep_rc(bst, mst, K,
             Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
             occ, ring_r, ring_c, do_contact,
             out_px, out_py, out_ct):
    """[MC] sweep() with sparse-ring contact.  Feasibility identical."""
    GH, GW = bst.shape[1], bst.shape[2]
    ny, nx = mst.shape[1], mst.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for c in range(nx):
                        if mst[k, r, c] and bst[k, base, gx + c]:
                            ok = False
                            break
            if not ok:
                continue
            ct = 0.0
            if do_contact:
                ct = _ct_rc(occ, gy, gx, GH, GW, ring_r, ring_c)
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True)
def sweep_pre_rc(bw, mw, K, ny, nx,
                 Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
                 occ, ring_r, ring_c, do_contact,
                 out_px, out_py, out_ct):
    """[MC] sweep_pre() with sparse-ring contact.  Word feasibility
    identical."""
    GH, GW = occ.shape[0], occ.shape[1]
    Wm = mw.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for w in range(Wm):
                        lo = gx + (w << 6)
                        wi = lo >> 6
                        s = lo & 63
                        seg = bw[k, base, wi] >> np.uint64(s)
                        if s > 0:
                            seg |= bw[k, base, wi + 1] << np.uint64(64 - s)
                        if mw[k, r, w] & seg:
                            ok = False
                            break
            if not ok:
                continue
            ct = 0.0
            if do_contact:
                ct = _ct_rc(occ, gy, gx, GH, GW, ring_r, ring_c)
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True, fastmath=True)
def sweep_l_rc(bst, mst, K,
               Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
               occ_st, lr_r, lr_c, l_off, do_contact,
               out_px, out_py, out_ct):
    """[MC] sweep_l() with per-layer sparse-ring contact."""
    GH, GW = bst.shape[1], bst.shape[2]
    ny, nx = mst.shape[1], mst.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for c in range(nx):
                        if mst[k, r, c] and bst[k, base, gx + c]:
                            ok = False
                            break
            if not ok:
                continue
            ct = 0.0
            if do_contact:
                ct = _ct_rc_l(occ_st, gy, gx, GH, GW, K, lr_r, lr_c, l_off)
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True, fastmath=True)
def sweep(bst, mst, K,
          Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
          occ, ring, do_contact,
          out_px, out_py, out_ct):
    """bst: (KB,GH,GW) uint8 blocked layers (KB >= K).  mst: (K,ny,nx) uint8
    masks.  occ: (GH,GW) uint8 layer-0 occupancy.  ring: (ny+2,nx+2) uint8.
    Returns number of feasible lattice positions written to out_* (BL order:
    py ascending, then px)."""
    GH, GW = bst.shape[1], bst.shape[2]
    ny, nx = mst.shape[1], mst.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for c in range(nx):
                        if mst[k, r, c] and bst[k, base, gx + c]:
                            ok = False
                            break
            if not ok:
                continue
            ct = 0.0
            if do_contact:
                for r in range(ny + 2):
                    yy = gy - 1 + r
                    for c in range(nx + 2):
                        if ring[r, c] == 0:
                            continue
                        xx = gx - 1 + c
                        if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
                            ct += 1.0  # bay wall counts as contact
                        elif occ[yy, xx]:
                            ct += 1.0
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True, fastmath=True)
def sweep_bits(bst, mst, K,
               Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
               occ, ring, do_contact,
               out_px, out_py, out_ct):
    """[BP] Bit-packed feasibility variant of sweep().  Same answer, same
    output order -- feasibility is word-level AND (64 cells/word) instead of
    the per-cell triple loop.  Contact term unchanged (boundary-only, no
    bit gain).  Blocked+mask packed to uint64 words once per call."""
    GH, GW = bst.shape[1], bst.shape[2]
    ny, nx = mst.shape[1], mst.shape[2]
    Wb = (GW + 63) // 64 + 1     # +1 guard word for cross-word reads
    Wm = (nx + 63) // 64
    one = np.uint64(1)
    # pack blocked rows -> words (bit x -> word x//64, pos x%64)
    bw = np.zeros((K, GH, Wb), np.uint64)
    for k in range(K):
        for y in range(GH):
            for x in range(GW):
                if bst[k, y, x]:
                    bw[k, y, x >> 6] |= (one << np.uint64(x & 63))
    # pack mask rows (padding bits stay 0 -> harmless in AND)
    mw = np.zeros((K, ny, Wm), np.uint64)
    for k in range(K):
        for r in range(ny):
            for c in range(nx):
                if mst[k, r, c]:
                    mw[k, r, c >> 6] |= (one << np.uint64(c & 63))
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for w in range(Wm):
                        lo = gx + (w << 6)          # abs bit of mask word's b0
                        wi = lo >> 6
                        s = lo & 63
                        seg = bw[k, base, wi] >> np.uint64(s)
                        if s > 0:
                            seg |= bw[k, base, wi + 1] << np.uint64(64 - s)
                        if mw[k, r, w] & seg:
                            ok = False
                            break
            if not ok:
                continue
            ct = 0.0
            if do_contact:
                for r in range(ny + 2):
                    yy = gy - 1 + r
                    for c in range(nx + 2):
                        if ring[r, c] == 0:
                            continue
                        xx = gx - 1 + c
                        if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
                            ct += 1.0
                        elif occ[yy, xx]:
                            ct += 1.0
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True, fastmath=True)
def pack_grid(bst, K, Wb):
    """Pack a (KB,GH,GW) uint8 blocked grid into (K,GH,Wb) uint64 words
    (bit x -> word x>>6, pos x&63).  Called ONCE at grid_cache build so the
    per-call feasibility sweep pays no packing cost (fixes the [BP] loss)."""
    GH, GW = bst.shape[1], bst.shape[2]
    bw = np.zeros((K, GH, Wb), np.uint64)
    one = np.uint64(1)
    for k in range(K):
        for y in range(GH):
            for x in range(GW):
                if bst[k, y, x]:
                    bw[k, y, x >> 6] |= (one << np.uint64(x & 63))
    return bw


@njit(cache=True, fastmath=True)
def sweep_pre(bw, mw, K, ny, nx,
              Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
              occ, ring, do_contact,
              out_px, out_py, out_ct):
    """[Morton/BP-cache] feasibility via word-AND on PRE-PACKED blocked (bw)
    and mask (mw) words -- no per-call packing.  Same answer/order as sweep().
    Contact unchanged (boundary-only)."""
    GH, GW = occ.shape[0], occ.shape[1]
    Wm = mw.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for w in range(Wm):
                        lo = gx + (w << 6)
                        wi = lo >> 6
                        s = lo & 63
                        seg = bw[k, base, wi] >> np.uint64(s)
                        if s > 0:
                            seg |= bw[k, base, wi + 1] << np.uint64(64 - s)
                        if mw[k, r, w] & seg:
                            ok = False
                            break
            if not ok:
                continue
            ct = 0.0
            if do_contact:
                for r in range(ny + 2):
                    yy = gy - 1 + r
                    for c in range(nx + 2):
                        if ring[r, c] == 0:
                            continue
                        xx = gx - 1 + c
                        if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
                            ct += 1.0
                        elif occ[yy, xx]:
                            ct += 1.0
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True)
def _clip_area_cell(vx, vy, n, xlo, xhi, ylo, yhi):
    """Area of a simple polygon clipped to an axis-aligned cell, via four
    sequential half-plane Sutherland-Hodgman passes.  For non-convex simple
    subjects SH may emit bridge edges, but they lie exactly ON the clip
    line, so the shoelace AREA of the output remains exact."""
    # working buffers (subject polygons stay tiny: < 32 verts after clips)
    ax = np.empty(64)
    ay = np.empty(64)
    bx = np.empty(64)
    by = np.empty(64)
    for i in range(n):
        ax[i] = vx[i]
        ay[i] = vy[i]
    m = n
    for side in range(4):
        k = 0
        for i in range(m):
            x1, y1 = ax[i], ay[i]
            j = (i + 1) % m
            x2, y2 = ax[j], ay[j]
            if side == 0:      # keep x >= xlo
                in1, in2 = x1 >= xlo, x2 >= xlo
                if in1 != in2:
                    t = (xlo - x1) / (x2 - x1)
                    ix, iy = xlo, y1 + t * (y2 - y1)
            elif side == 1:    # keep x <= xhi
                in1, in2 = x1 <= xhi, x2 <= xhi
                if in1 != in2:
                    t = (xhi - x1) / (x2 - x1)
                    ix, iy = xhi, y1 + t * (y2 - y1)
            elif side == 2:    # keep y >= ylo
                in1, in2 = y1 >= ylo, y2 >= ylo
                if in1 != in2:
                    t = (ylo - y1) / (y2 - y1)
                    ix, iy = x1 + t * (x2 - x1), ylo
            else:              # keep y <= yhi
                in1, in2 = y1 <= yhi, y2 <= yhi
                if in1 != in2:
                    t = (yhi - y1) / (y2 - y1)
                    ix, iy = x1 + t * (x2 - x1), yhi
            if in1:
                bx[k] = x1
                by[k] = y1
                k += 1
            if in1 != in2:
                bx[k] = ix
                by[k] = iy
                k += 1
        m = k
        if m == 0:
            return 0.0
        for i in range(m):
            ax[i] = bx[i]
            ay[i] = by[i]
    s = 0.0
    for i in range(m):
        j = (i + 1) % m
        s += ax[i] * ay[j] - ax[j] * ay[i]
    return abs(s) * 0.5


@njit(cache=True)
def poly_cell_areas(vx, vy, cx0, cy0, nx, ny, S, out):
    """Exact intersection area of the polygon with every cell of the grid
    frame (cells are 1/S x 1/S, cell (r, c) spans
    [(cx0+c)/S, (cx0+c+1)/S) x [(cy0+r)/S, (cy0+r+1)/S))."""
    n = vx.shape[0]
    inv = 1.0 / S
    for r in range(ny):
        ylo = (cy0 + r) * inv
        yhi = ylo + inv
        for c in range(nx):
            xlo = (cx0 + c) * inv
            out[r, c] = _clip_area_cell(vx, vy, n, xlo, xlo + inv, ylo, yhi)


@njit(cache=True, fastmath=True)
def sweep_l(bst, mst, K,
            Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
            occ_st, rings, do_contact,
            out_px, out_py, out_ct):
    """E3 layer-accounted variant of sweep: occ_st (KO,GH,GW) per-layer
    occupancy, rings (K,ny+2,nx+2) per-layer contact rings.  Contact is the
    sum over layers of ring-k adjacency to layer-k occupancy or bay wall."""
    GH, GW = bst.shape[1], bst.shape[2]
    ny, nx = mst.shape[1], mst.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for c in range(nx):
                        if mst[k, r, c] and bst[k, base, gx + c]:
                            ok = False
                            break
            if not ok:
                continue
            ct = 0.0
            if do_contact:
                for k in range(K):
                    for r in range(ny + 2):
                        yy = gy - 1 + r
                        for c in range(nx + 2):
                            if rings[k, r, c] == 0:
                                continue
                            xx = gx - 1 + c
                            if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
                                ct += 1.0  # bay wall exists at every layer
                            elif occ_st[k, yy, xx]:
                                ct += 1.0
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True, fastmath=True)
def sweep_a(bst, mst, K,
            Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
            exq, ring, exit_c, W, do_contact,
            out_px, out_py, out_ct):
    """P-A (temporal coherence) variant of sweep: contact counts only
    ALIGNED neighbours -- the wall (never leaves: it cannot fragment
    time) and blocks whose exit is within W of the candidate's exit_c.
    exq: (GH,GW) int32, exit time of the layer-0 occupant, -1 if free."""
    GH, GW = bst.shape[1], bst.shape[2]
    ny, nx = mst.shape[1], mst.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for c in range(nx):
                        if mst[k, r, c] and bst[k, base, gx + c]:
                            ok = False
                            break
            if not ok:
                continue
            ct = 0.0
            if do_contact:
                for r in range(ny + 2):
                    yy = gy - 1 + r
                    for c in range(nx + 2):
                        if ring[r, c] == 0:
                            continue
                        xx = gx - 1 + c
                        if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
                            ct += 1.0  # wall = eternally aligned
                        else:
                            e = exq[yy, xx]
                            if e >= 0 and abs(e - exit_c) <= W:
                                ct += 1.0
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True, fastmath=True)
def sweep_pk(bst, mst, K,
             Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
             occ, ring, do_contact,
             out_px, out_py, out_ct):
    """P-B (dead-space) variant: contact MINUS the pocket delta.  A pocket
    is a free cell with >=3 of its 4 neighbours in (occupied | wall); the
    placement is charged for the pockets it CREATES in the 1-cell band
    around the new block (both terms in cells -> no weight knob)."""
    GH, GW = bst.shape[1], bst.shape[2]
    ny, nx = mst.shape[1], mst.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for c in range(nx):
                        if mst[k, r, c] and bst[k, base, gx + c]:
                            ok = False
                            break
            if not ok:
                continue
            ct = 0.0
            if do_contact:
                for r in range(ny + 2):
                    yy = gy - 1 + r
                    for c in range(nx + 2):
                        if ring[r, c] == 0:
                            continue
                        xx = gx - 1 + c
                        if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
                            ct += 1.0
                            continue
                        if occ[yy, xx]:
                            ct += 1.0
                            continue
                        # free ring cell: pocket-status delta
                        nb_b = 0  # blocked neighbours before placement
                        nb_a = 0  # after (incl. the new block's cells)
                        for d in range(4):
                            if d == 0:
                                y2, x2 = yy - 1, xx
                            elif d == 1:
                                y2, x2 = yy + 1, xx
                            elif d == 2:
                                y2, x2 = yy, xx - 1
                            else:
                                y2, x2 = yy, xx + 1
                            if (y2 < 0 or y2 >= GH
                                    or x2 < 0 or x2 >= GW):
                                nb_b += 1
                                nb_a += 1
                                continue
                            if occ[y2, x2]:
                                nb_b += 1
                                nb_a += 1
                                continue
                            r2 = y2 - gy
                            c2 = x2 - gx
                            if (0 <= r2 < ny and 0 <= c2 < nx
                                    and mst[0, r2, c2]):
                                nb_a += 1
                        if nb_a >= 3 and nb_b < 3:
                            ct -= 1.0  # newly created pocket
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[n] = ct
                n += 1
    return n


@njit(cache=True, fastmath=True)
def sweep_multi(bst, mst, K,
                Sc, cx0, cy0, px_lo, px_hi, py_lo, py_hi,
                occ, exq, ring, exit_c, w25, w50, do_contact,
                out_px, out_py, out_ct):
    """[M] fused multi-lens sweep: ONE shared feasibility pass, ONE ring
    pass computing the three stage-1 lens contacts simultaneously.
    out_ct: (3, cap) float32 -- rows are [base, a25, a50].
    Bit-compat contract: row 0 == sweep()'s ct; rows 1/2 == sweep_a()'s ct
    at W=w25/w50 for identical inputs (verified by unit test)."""
    GH, GW = bst.shape[1], bst.shape[2]
    ny, nx = mst.shape[1], mst.shape[2]
    cap = out_px.shape[0]
    n = 0
    for py in range(py_lo, py_hi + 1):
        gy = py * Sc + cy0
        for px in range(px_lo, px_hi + 1):
            gx = px * Sc + cx0
            ok = True
            for k in range(K):
                if not ok:
                    break
                for r in range(ny):
                    if not ok:
                        break
                    base = gy + r
                    for c in range(nx):
                        if mst[k, r, c] and bst[k, base, gx + c]:
                            ok = False
                            break
            if not ok:
                continue
            c0 = 0.0
            c1 = 0.0
            c2 = 0.0
            if do_contact:
                for r in range(ny + 2):
                    yy = gy - 1 + r
                    for c in range(nx + 2):
                        if ring[r, c] == 0:
                            continue
                        xx = gx - 1 + c
                        if yy < 0 or yy >= GH or xx < 0 or xx >= GW:
                            c0 += 1.0  # wall: contact for base,
                            c1 += 1.0  # eternally aligned for both alphas
                            c2 += 1.0
                        else:
                            if occ[yy, xx]:
                                c0 += 1.0
                            e = exq[yy, xx]
                            if e >= 0:
                                d = e - exit_c
                                if d < 0:
                                    d = -d
                                if d <= w25:
                                    c1 += 1.0
                                if d <= w50:
                                    c2 += 1.0
            if n < cap:
                out_px[n] = px
                out_py[n] = py
                out_ct[0, n] = c0
                out_ct[1, n] = c1
                out_ct[2, n] = c2
                n += 1
    return n


_CAP = 4096
_out_px = np.empty(_CAP, dtype=np.int32)
_out_py = np.empty(_CAP, dtype=np.int32)
_out_ct = np.empty(_CAP, dtype=np.float32)
_out_ct3 = np.empty((3, _CAP), dtype=np.float32)
_out_px2 = np.empty(_CAP, dtype=np.int32)  # [MC] MCCHK audit buffers
_out_py2 = np.empty(_CAP, dtype=np.int32)
_out_ct2 = np.empty(_CAP, dtype=np.float32)


def sweep_positions_pre(blocked_w, geo, Sc, px_lo, px_hi, py_lo, py_hi,
                        occ0, do_contact=True):
    """[Morton/BP-cache] base-sweep with PRE-PACKED blocked words (from the
    grid_cache) + geo.masks_w -- no per-call packing.  Byte-identical to
    sweep_positions' base path."""
    if isinstance(occ0, np.ndarray) and occ0.dtype == np.uint8:
        occ = occ0
    else:
        occ = (occ0 > 0.5).astype(np.uint8)
    if _MC and not _MCCHK:  # [MC] sparse-ring contact on the word path
        n = sweep_pre_rc(blocked_w, geo.masks_w, geo.K, geo.ny, geo.nx,
                         Sc, geo.cx0, geo.cy0, px_lo, px_hi, py_lo, py_hi,
                         occ, geo.ring_r, geo.ring_c,
                         1 if do_contact else 0,
                         _out_px, _out_py, _out_ct)
    else:
        n = sweep_pre(blocked_w, geo.masks_w, geo.K, geo.ny, geo.nx,
                      Sc, geo.cx0, geo.cy0, px_lo, px_hi, py_lo, py_hi,
                      occ, geo.ring_u8, 1 if do_contact else 0,
                      _out_px, _out_py, _out_ct)
        if _MC and _MCCHK and do_contact:  # audit: both, exact equal
            n2 = sweep_pre_rc(blocked_w, geo.masks_w, geo.K, geo.ny,
                              geo.nx, Sc, geo.cx0, geo.cy0, px_lo, px_hi,
                              py_lo, py_hi, occ, geo.ring_r, geo.ring_c,
                              1, _out_px2, _out_py2, _out_ct2)
            assert n2 == n and (_out_ct2[:n] == _out_ct[:n]).all() \
                and (_out_px2[:n] == _out_px[:n]).all() \
                and (_out_py2[:n] == _out_py[:n]).all(), \
                "MCCHK sweep_pre_rc mismatch"
    return (_out_px[:n].copy(), _out_py[:n].copy(),
            _out_ct[:n].astype(np.float64).copy())


def sweep_positions_multi(blocked, geo, Sc, px_lo, px_hi, py_lo, py_hi,
                          occ0, exq, exit_c, w25, w50, do_contact=True):
    """[M] wrapper: one pass -> (pxs, pys, ct(3, n) [base, a25, a50])."""
    if isinstance(blocked, np.ndarray) and blocked.dtype == np.uint8:
        bst = blocked
    else:
        bst = np.stack([(b > 0.5) for b in blocked]).astype(np.uint8)
    if isinstance(occ0, np.ndarray) and occ0.dtype == np.uint8:
        occ = occ0
    else:
        occ = (occ0 > 0.5).astype(np.uint8)
    n = sweep_multi(bst, geo.masks_u8, geo.K, Sc, geo.cx0, geo.cy0,
                    px_lo, px_hi, py_lo, py_hi, occ, exq, geo.ring_u8,
                    int(exit_c), int(w25), int(w50),
                    1 if do_contact else 0, _out_px, _out_py, _out_ct3)
    return (_out_px[:n].copy(), _out_py[:n].copy(),
            _out_ct3[:, :n].astype(np.float64).copy())


def sweep_positions(blocked, geo, Sc, px_lo, px_hi, py_lo, py_hi,
                    occ0, do_contact=True, occ_st=None,
                    exq=None, exit_c=0, w_al=0, pk=False):
    """Python-friendly wrapper.  blocked: pre-stacked (KMAX,GH,GW) uint8
    array (S1/S3 cache format) or a list of KMAX float32 grids (legacy);
    geo: OrientGeo.  Returns (pxs, pys, contact).
    occ_st: optional per-layer occupancy (stacked uint8 or list of grids)
    -> E3 layered contact (sum over layers) instead of the layer-0 ring.
    exq: optional (GH,GW) int32 exit-time grid -> P-A aligned contact
    (|exit_neighbour - exit_c| <= w_al, wall always aligned)."""
    if isinstance(blocked, np.ndarray) and blocked.dtype == np.uint8:
        bst = blocked  # S1: cached grids are already sweep-ready
    else:
        bst = np.stack([(b > 0.5) for b in blocked]).astype(np.uint8)
    mst = geo.masks_u8  # S1: pre-stacked once per OrientGeo
    if exq is not None:
        if _SV and not _SVCHK:  # [SV v19.7] sparse-list E_AL sweep
            n = sweep_a_sv(bst, geo.K, Sc, geo.cx0, geo.cy0,
                           px_lo, px_hi, py_lo, py_hi, exq,
                           geo.mv_r, geo.mv_c, geo.mv_off,
                           geo.ring_r, geo.ring_c,
                           int(exit_c), int(w_al),
                           1 if do_contact else 0,
                           _out_px, _out_py, _out_ct)
        else:
            n = sweep_a(bst, mst, geo.K, Sc, geo.cx0, geo.cy0,
                        px_lo, px_hi, py_lo, py_hi, exq, geo.ring_u8,
                        int(exit_c), int(w_al),
                        1 if do_contact else 0, _out_px, _out_py, _out_ct)
            if _SV and _SVCHK and do_contact:  # audit: both, exact equal
                n2 = sweep_a_sv(bst, geo.K, Sc, geo.cx0, geo.cy0,
                                px_lo, px_hi, py_lo, py_hi, exq,
                                geo.mv_r, geo.mv_c, geo.mv_off,
                                geo.ring_r, geo.ring_c,
                                int(exit_c), int(w_al), 1,
                                _out_px2, _out_py2, _out_ct2)
                assert n2 == n and (_out_ct2[:n] == _out_ct[:n]).all() \
                    and (_out_px2[:n] == _out_px[:n]).all() \
                    and (_out_py2[:n] == _out_py[:n]).all(), \
                    "SVCHK sweep_a_sv mismatch"
    elif pk:
        if isinstance(occ0, np.ndarray) and occ0.dtype == np.uint8:
            occp = occ0
        else:
            occp = (occ0 > 0.5).astype(np.uint8)
        n = sweep_pk(bst, mst, geo.K, Sc, geo.cx0, geo.cy0,
                     px_lo, px_hi, py_lo, py_hi, occp, geo.ring_u8,
                     1 if do_contact else 0, _out_px, _out_py, _out_ct)
    elif occ_st is not None:
        if isinstance(occ_st, np.ndarray) and occ_st.dtype == np.uint8:
            occs = occ_st
        else:
            occs = np.stack([(o > 0.5) for o in occ_st]).astype(np.uint8)
        if _MC and not _MCCHK:  # [MC] sparse-ring layered contact
            n = sweep_l_rc(bst, mst, geo.K, Sc, geo.cx0, geo.cy0,
                           px_lo, px_hi, py_lo, py_hi, occs,
                           geo.lring_r, geo.lring_c, geo.lring_off,
                           1 if do_contact else 0,
                           _out_px, _out_py, _out_ct)
        else:
            n = sweep_l(bst, mst, geo.K, Sc, geo.cx0, geo.cy0,
                        px_lo, px_hi, py_lo, py_hi, occs, geo.rings_u8,
                        1 if do_contact else 0, _out_px, _out_py, _out_ct)
            if _MC and _MCCHK and do_contact:  # audit: both, exact equal
                n2 = sweep_l_rc(bst, mst, geo.K, Sc, geo.cx0, geo.cy0,
                                px_lo, px_hi, py_lo, py_hi, occs,
                                geo.lring_r, geo.lring_c, geo.lring_off,
                                1, _out_px2, _out_py2, _out_ct2)
                assert n2 == n and (_out_ct2[:n] == _out_ct[:n]).all() \
                    and (_out_px2[:n] == _out_px[:n]).all() \
                    and (_out_py2[:n] == _out_py[:n]).all(), \
                    "MCCHK sweep_l_rc mismatch"
    else:
        if isinstance(occ0, np.ndarray) and occ0.dtype == np.uint8:
            occ = occ0
        else:
            occ = (occ0 > 0.5).astype(np.uint8)
        if _MC and not _MCCHK and not _BITPACK:
            n = sweep_rc(bst, mst, geo.K, Sc, geo.cx0, geo.cy0,
                         px_lo, px_hi, py_lo, py_hi, occ,
                         geo.ring_r, geo.ring_c,
                         1 if do_contact else 0,
                         _out_px, _out_py, _out_ct)
        else:
            _sw = sweep_bits if _BITPACK else sweep
            n = _sw(bst, mst, geo.K, Sc, geo.cx0, geo.cy0,
                    px_lo, px_hi, py_lo, py_hi, occ, geo.ring_u8,
                    1 if do_contact else 0, _out_px, _out_py, _out_ct)
            if _MC and _MCCHK and do_contact:  # audit: both, exact equal
                n2 = sweep_rc(bst, mst, geo.K, Sc, geo.cx0, geo.cy0,
                              px_lo, px_hi, py_lo, py_hi, occ,
                              geo.ring_r, geo.ring_c, 1,
                              _out_px2, _out_py2, _out_ct2)
                assert n2 == n and (_out_ct2[:n] == _out_ct[:n]).all() \
                    and (_out_px2[:n] == _out_px[:n]).all() \
                    and (_out_py2[:n] == _out_py[:n]).all(), \
                    "MCCHK sweep_rc mismatch"
    return (_out_px[:n].copy(), _out_py[:n].copy(),
            _out_ct[:n].astype(np.float64).copy())
@njit(cache=True)
def _pip(px_, py_, v, ox, oy, eps):
    """[EXN] point-in-polygon (crossing number), 3-valued: 1 inside,
    0 outside, 2 uncertain (ray near a vertex / point near boundary --
    delegate).  v: (n,2) base ring, +(ox,oy) translation."""
    n = v.shape[0]
    cnt = 0
    for i in range(n):
        y1 = v[i, 1] + oy
        i2 = i + 1 if i + 1 < n else 0
        y2 = v[i2, 1] + oy
        if abs(y1 - py_) < 1e-9 or abs(y2 - py_) < 1e-9:
            return 2          # horizontal ray grazes a vertex -> uncertain
        if (y1 > py_) != (y2 > py_):
            x1 = v[i, 0] + ox
            x2 = v[i2, 0] + ox
            xint = x1 + (py_ - y1) * (x2 - x1) / (y2 - y1)
            if abs(xint - px_) < eps:
                return 2      # point ~on an edge -> uncertain
            if xint > px_:
                cnt += 1
    return cnt & 1


@njit(cache=True)
def _pt_seg2(px_, py_, x1, y1, x2, y2):
    """squared distance from point to segment"""
    dx = x2 - x1
    dy = y2 - y1
    L2 = dx * dx + dy * dy
    if L2 <= 0.0:
        ex = px_ - x1
        ey = py_ - y1
        return ex * ex + ey * ey
    t = ((px_ - x1) * dx + (py_ - y1) * dy) / L2
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    ex = px_ - (x1 + t * dx)
    ey = py_ - (y1 + t * dy)
    return ex * ex + ey * ey


@njit(cache=True)
def poly_verdict(va, ax, ay, vb, bx, by):
    """[EXN] 3-valued overlap verdict for translated simple polygons
    A = va+(ax,ay), B = vb+(bx,by):
      1 = SURE_OVERLAP  (intersection area > 0, mathematically certain)
      0 = SURE_DISJOINT (intersection area == 0, certain)
      2 = AMBIGUOUS     (near-degenerate -> delegate to shapely)
    Sufficient conditions ONLY -- a SURE answer always agrees with the
    exact `inter.area > 0` test, so substituting it is byte-identical.
      * certain proper edge crossing            -> 1
      * potential crossing without certainty    -> 2 (touch / collinear)
      * boundaries closer than EPS anywhere     -> 2
      * boundaries clear + a vertex strictly
        inside the other (containment!)         -> 1
      * boundaries clear + both outside         -> 0
    The containment check is the fix for the original prompt's
    SURE_DISJOINT flaw ("all edge pairs far apart" misses A entirely
    inside B).  EPS = 1e-6 absolute (coords O(1..1e3); exact touches in
    packings are distance 0, genuine gaps >= raster steps >> EPS)."""
    EPS = 1e-6
    EPS2 = EPS * EPS
    na = va.shape[0]
    nb = vb.shape[0]
    for i in range(na):
        x1 = va[i, 0] + ax
        y1 = va[i, 1] + ay
        i2 = i + 1 if i + 1 < na else 0
        x2 = va[i2, 0] + ax
        y2 = va[i2, 1] + ay
        d1x = x2 - x1
        d1y = y2 - y1
        for j in range(nb):
            x3 = vb[j, 0] + bx
            y3 = vb[j, 1] + by
            j2 = j + 1 if j + 1 < nb else 0
            x4 = vb[j2, 0] + bx
            y4 = vb[j2, 1] + by
            d2x = x4 - x3
            d2y = y4 - y3
            o1 = d1x * (y3 - y1) - d1y * (x3 - x1)
            o2 = d1x * (y4 - y1) - d1y * (x4 - x1)
            o3 = d2x * (y1 - y3) - d2y * (x1 - x3)
            o4 = d2x * (y2 - y3) - d2y * (x2 - x3)
            # orientation certainty bands: float error is ~1e-16 * scale,
            # the band 1e-9 * scale is far above it, so |o| > band means
            # the exact sign matches (scale-safe sufficiency)
            s1 = d1x * d1x + d1y * d1y
            s2 = d2x * d2x + d2y * d2y
            t1 = 1e-9 * (s1 + (x3 - x1) * (x3 - x1) + (y3 - y1) * (y3 - y1)
                         + 1.0)
            t2 = 1e-9 * (s1 + (x4 - x1) * (x4 - x1) + (y4 - y1) * (y4 - y1)
                         + 1.0)
            t3 = 1e-9 * (s2 + (x1 - x3) * (x1 - x3) + (y1 - y3) * (y1 - y3)
                         + 1.0)
            t4 = 1e-9 * (s2 + (x2 - x3) * (x2 - x3) + (y2 - y3) * (y2 - y3)
                         + 1.0)
            cross_a = (o1 > t1 and o2 < -t2) or (o1 < -t1 and o2 > t2)
            cross_b = (o3 > t3 and o4 < -t4) or (o3 < -t3 and o4 > t4)
            if cross_a and cross_b:
                return 1      # certain proper crossing -> area > 0
            # potential crossing (signs not certainly separating) -> the
            # exact test could go either way (touch, collinear overlap):
            if o1 * o2 <= 0.0 and o3 * o4 <= 0.0:
                if not (abs(o1) > t1 and abs(o2) > t2
                        and abs(o3) > t3 and abs(o4) > t4):
                    return 2
                # both products certainly <= 0 with certain signs but not
                # a proper double-crossing: endpoints sit on opposite
                # closures -> segments certainly intersect -> area check
                # is still ambiguous only if they merely touch; a certain
                # strict sign on all four means a proper crossing, which
                # cross_a/cross_b would have caught -- anything else here
                # is a T-touch -> delegate
                return 2
            # clearly non-crossing pair: near-touch guard
            d2 = _pt_seg2(x3, y3, x1, y1, x2, y2)
            dd = _pt_seg2(x4, y4, x1, y1, x2, y2)
            if dd < d2:
                d2 = dd
            dd = _pt_seg2(x1, y1, x3, y3, x4, y4)
            if dd < d2:
                d2 = dd
            dd = _pt_seg2(x2, y2, x3, y3, x4, y4)
            if dd < d2:
                d2 = dd
            if d2 <= EPS2:
                return 2      # boundaries touch/graze -> delegate
    # boundaries are everywhere > EPS apart -> either fully disjoint or
    # one polygon strictly contains the other
    ra = _pip(va[0, 0] + ax, va[0, 1] + ay, vb, bx, by, EPS)
    if ra == 2:
        return 2
    if ra == 1:
        return 1              # A's vertex strictly inside B -> area > 0
    rb = _pip(vb[0, 0] + bx, vb[0, 1] + by, va, ax, ay, EPS)
    if rb == 2:
        return 2
    if rb == 1:
        return 1
    return 0                  # both outside, boundaries clear -> area == 0



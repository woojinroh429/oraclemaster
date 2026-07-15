"""
FFT crane-feasibility-map POC (self-contained, real block shapes).

Crane rule: NEW block feasible at (x,y) iff for every layer k of NEW, its footprint
shifted to (x,y) does NOT overlap the cumulative obstacle mask O_k = union of all
existing occupancy at absolute layers >= k.

Overlap area for ALL (x,y) at once = cross-correlation O_k star NEW_k via FFT.
fft(O_k) is bay-state-only -> computed once, reused for every candidate block.

Validates: FFT feasible-map == brute per-position feasible-map, and times both,
across bay sizes (95x26 real prob_28, plus scaled-up synthetic to model P5/P6).
"""
import sys, time, json
import numpy as np

def rasterize(verts, W, H, ox=0.0, oy=0.0):
    verts = np.asarray(verts, float) + np.array([ox, oy])
    if len(verts) < 3:
        return np.zeros((H, W), bool)
    x0 = max(0, int(np.floor(verts[:,0].min()))); x1 = min(W, int(np.ceil(verts[:,0].max())))
    y0 = max(0, int(np.floor(verts[:,1].min()))); y1 = min(H, int(np.ceil(verts[:,1].max())))
    if x1 <= x0 or y1 <= y0:
        return np.zeros((H, W), bool)
    xs = np.arange(x0, x1) + 0.5; ys = np.arange(y0, y1) + 0.5
    gx, gy = np.meshgrid(xs, ys)
    inside = np.zeros(gx.shape, bool); n = len(verts); j = n-1
    for i in range(n):
        xi, yi = verts[i]; xj, yj = verts[j]
        cond = ((yi > gy) != (yj > gy)) & (gx < (xj-xi)*(gy-yi)/(yj-yi+1e-12) + xi)
        inside ^= cond; j = i
    full = np.zeros((H, W), bool); full[y0:y1, x0:x1] = inside
    return full

def cumulative_obstacles(placed, W, H, maxL):
    """placed: list of (layer_masks_at_pos). Return O_k for k in 0..maxL-1 where
    O_k = union over blocks and their layers j>=k of that layer's mask."""
    # First accumulate raw occupancy per absolute layer.
    raw = [np.zeros((H, W), bool) for _ in range(maxL)]
    for masks in placed:
        for j, m in enumerate(masks):
            if j < maxL:
                raw[j] |= m
    # O_k = union over j>=k raw[j]  (suffix-union)
    Ok = [None]*maxL
    acc = np.zeros((H, W), bool)
    for k in range(maxL-1, -1, -1):
        acc = acc | raw[k]
        Ok[k] = acc.copy()
    return Ok

def brute_feasible(Ok, new_masks, W, H):
    """For each (x,y) integer translation, shift each new layer mask and test overlap
    with Ok[k]. Feasible if no overlap for any k AND stays in bounds. O(positions*cells)."""
    feas = np.zeros((H, W), bool)
    # bounding box of the new block footprint (union of its layers)
    union = np.zeros((H, W), bool)
    for m in new_masks: union |= m
    ys, xs = np.where(union)
    if len(xs) == 0: return feas
    bw = xs.max()+1; bh = ys.max()+1
    for oy in range(0, H-bh+1):
        for ox in range(0, W-bw+1):
            ok = True
            for k, m in enumerate(new_masks):
                if k >= len(Ok): break
                # shift mask by (ox,oy): overlap = any(Ok[k][oy:.., ox:..] & m[:h,:w])
                sub = Ok[k][oy:oy+bh, ox:ox+bw]
                if np.any(sub & m[:bh, :bw]):
                    ok = False; break
            if ok: feas[oy, ox] = True
    return feas

def fft_feasible(Ok, new_masks, W, H):
    """Feasibility map for all translations via FFT cross-correlation.
    overlap_k[oy,ox] = sum over cells of Ok[k] AND new_k shifted to (ox,oy).
    Using correlation: corr = ifft2( fft2(Ok) * conj(fft2(new_k)) ), aligned so that
    index (oy,ox) = placing new block's local origin at (ox,oy)."""
    # pad to avoid wraparound; use size >= W+bw, H+bh
    union = np.zeros((H, W), bool)
    for m in new_masks: union |= m
    ys, xs = np.where(union)
    bw = xs.max()+1 if len(xs) else 1; bh = ys.max()+1 if len(ys) else 1
    fh = H + bh; fw = W + bw
    infeas = np.zeros((fh, fw))
    for k, m in enumerate(new_masks):
        if k >= len(Ok): break
        O = Ok[k].astype(np.float64)
        N = m[:bh, :bw].astype(np.float64)
        FO = np.fft.rfft2(O, s=(fh, fw))
        FN = np.fft.rfft2(N[::-1, ::-1], s=(fh, fw))   # correlation via flipped kernel
        corr = np.fft.irfft2(FO * FN, s=(fh, fw))
        infeas += corr
    # valid placement origins (ox,oy) with block fully in-bounds and zero overlap.
    # correlation of flipped kernel puts origin at offset (bh-1, bw-1).
    feas = np.zeros((H, W), bool)
    region = infeas[bh-1:bh-1+H, bw-1:bw-1+W]
    inb = np.zeros((H, W), bool)
    inb[:H-bh+1, :W-bw+1] = True
    feas = (region < 0.5) & inb
    return feas

def build_state(inst, K, W, H, seed_positions):
    blocks = inst["blocks"]
    placed = []; maxL = 0
    for idx, (bid, ox, oy) in enumerate(seed_positions[:K]):
        layers = blocks[bid]["shape"][0]["layers"]
        masks = [rasterize(l, W, H, ox, oy) for l in layers]
        placed.append(masks); maxL = max(maxL, len(masks))
    return placed, maxL

def main():
    inst = json.load(open("../data/train/prob_28.json"))
    blocks = inst["blocks"]
    # deterministic pseudo-positions spreading blocks across a chosen bay size.
    for (W, H, tag) in [(95, 26, "real prob_28"), (300, 120, "synthetic ~P5/P6")]:
        # place K blocks at a grid of offsets
        K = min(20, len(blocks))
        seed = []
        gx = 0; gy = 0
        for bid in range(K):
            layers = blocks[bid]["shape"][0]["layers"]
            verts = np.asarray(layers[0], float)
            bw = int(verts[:,0].max()-verts[:,0].min())+2
            bh = int(verts[:,1].max()-verts[:,1].min())+2
            if gx + bw >= W: gx = 0; gy += bh
            if gy + bh >= H: break
            seed.append((bid, gx - verts[:,0].min(), gy - verts[:,1].min()))
            gx += bw
        placed, maxL = build_state(inst, len(seed), W, H, seed)
        Ok = cumulative_obstacles(placed, W, H, maxL)
        occ = sum(int(o.sum()) for o in Ok)
        # candidate block = a fresh one
        cand = blocks[K % len(blocks)]["shape"][0]["layers"]
        new_masks = [rasterize(l, W, H, -np.asarray(l,float)[:,0].min(),
                               -np.asarray(l,float)[:,1].min()) for l in cand]

        t0=time.time(); fb = brute_feasible(Ok, new_masks, W, H); tb=time.time()-t0
        t0=time.time(); ff = fft_feasible(Ok, new_masks, W, H); tf=time.time()-t0
        agree = int((fb == ff).sum()); total = W*H
        disagree = total - agree
        print(f"[{tag}] {W}x{H} placed={len(seed)} maxL={maxL} | "
              f"brute={fb.sum()} fft={ff.sum()} feas positions | "
              f"disagree={disagree}/{total} | brute={tb*1000:.1f}ms fft={tf*1000:.1f}ms "
              f"speedup={tb/max(tf,1e-9):.1f}x")
    print("ALLDONE")

if __name__ == "__main__":
    main()

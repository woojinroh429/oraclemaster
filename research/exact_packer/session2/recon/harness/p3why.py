"""Why does a LESS full bay take more blocks?

The measurement that started this: turning candidate contact off (conw=0.0) reaches 87,560 on
P3 where contact at full strength reaches 96,990, and the whole difference is Z3 -- 462 against
543 -- which on this instance means 81 more blocks got into the bay they wanted.  A packer that
presses blocks together admits FEWER of them.  That is backwards for area and exactly right for
the crane, and the point of this script is to say which of several possible reasons it is,
in numbers, rather than to assert the obvious-sounding one.

The rule, precisely.  A block descends vertically and may only land where, for each of its
layers k, no already-resting block occupies that cell at a layer j >= k.  Two consequences that
pull in opposite directions:

  * layer 0 needs cells that are completely empty, so at the floor the constraint is ordinary
    2-D packing and pressing blocks together is free -- area is area however it is arranged
  * every layer above 0 must clear whatever sits BELOW it along the same column, so a block
    whose upper layers overhang its own base needs the neighbouring cells to be short or empty

If the second is what matters, then the cost of contact packing is that it fills the margins an
overhang needs, and the fix is not "less contact" but "keep the margins around tall things".
That is a different term from the one we have, and a much more selective one.

Four measurements, on two solutions from the same instance:

  [1] AREA        peak and mean occupied cells in the contested bay, per time step.  If the
                  flat solution simply holds less area, nothing subtle is happening and the
                  gain is a scheduling accident.
  [2] ADMISSION   for every block in the instance, the number of cells in the contested bay
                  where it could legally land at its own entry time, against the solution's
                  own residents.  This is the quantity the objective actually cares about,
                  measured directly instead of inferred.
  [3] HEIGHT MAP  the distribution of per-cell stack height.  Contact packing should show
                  more cells at height >= 1 next to each other; flat packing more isolated
                  ones surrounded by height 0.
  [4] OVERHANG    per block, whether its upper layers extend beyond its layer-0 footprint, and
                  whether admission in [2] correlates with it.  This is the discriminating
                  test: if only overhanging blocks benefit from the flat layout, the mechanism
                  is the margin, and a term that protects margins beats one that suppresses
                  contact everywhere.

    python3.12 harness/p3why.py [PROB] [SECONDS] [MOD_A] [MOD_B]
"""
import importlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402
from utils import Block          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
MODS = (sys.argv[3] if len(sys.argv) > 3 else "myalg_base",
        sys.argv[4] if len(sys.argv) > 4 else "myalg_c0ctl")

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
w2, w3 = float(w["w2"]), float(w["w3"])
pref = [B[b]["bay_preferences"] for b in range(n)]
mxp = [max(pref[b]) for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
pt = [int(B[b]["processing_time"]) for b in range(n)]
bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]


# --------------------------------------------------------------------------------------
# [4] OVERHANG is a property of the INSTANCE, not of a solution, so it is computed once.
# A block overhangs when some layer above 0 covers a cell its layer 0 does not: those are the
# cells that must be short or empty in the neighbourhood, and they are the only reason the
# arrangement of everything else can matter beyond plain area.
# --------------------------------------------------------------------------------------
def cells_of(bid, oi, layer=None):
    blk = Block(block_id=bid, block_data=B[bid], x=0, y=0, orient_idx=oi)
    Ls = blk.layers_at_pos()
    out = []
    for k, L in enumerate(Ls):
        if layer is not None and k != layer:
            continue
        xs = [p[0] for p in L]; ys = [p[1] for p in L]
        out.append((k, math.floor(min(xs)), math.floor(min(ys)),
                    math.ceil(max(xs)), math.ceil(max(ys)), len(Ls)))
    return out


over = [0] * n
nlay = [1] * n
for b in range(n):
    worst = 0
    for oi in range(len(B[b]["shape"])):
        cs = cells_of(b, oi)
        nlay[b] = max(nlay[b], cs[0][5])
        if len(cs) < 2:
            continue
        _, bx0, by0, bx1, by1, _ = cs[0]
        for (k, x0, y0, x1, y1, _nl) in cs[1:]:
            ex = max(0, bx0 - x0) + max(0, x1 - bx1) + max(0, by0 - y0) + max(0, y1 - by1)
            worst = max(worst, ex)
    over[b] = worst

print("P%d: %d blocks, %d bays.  layers per block: %s"
      % (PROB, n, m, {k: sum(1 for b in range(n) if nlay[b] == k) for k in sorted(set(nlay))}))
print("   overhang (upper layers extending past layer 0, in cells of bbox margin):")
print("      none %d,  1-2 %d,  3-5 %d,  6+ %d"
      % (sum(1 for x in over if x == 0), sum(1 for x in over if 1 <= x <= 2),
         sum(1 for x in over if 3 <= x <= 5), sum(1 for x in over if x >= 6)), flush=True)
if not any(over):
    print("   -> NO block overhangs its own base in any orientation.  Then the descent rule")
    print("      cannot be about margins at all: with every footprint a straight prism, layer 0")
    print("      decides everything and the rule reduces to plain 2-D packing plus time.")
    print("      Whatever conw=0.0 is buying, it is not overhang clearance -- read [2] for what")
    print("      it is instead.", flush=True)

E = SC._ogc_fast_engine(d)
rows = {}
for MOD in MODS:
    sol = importlib.import_module(MOD).algorithm(d, SECS)
    o, c = SC._total(d, sol)
    cur, ent, ext, place = [0] * n, {}, {}, {}
    for t, ops in sol["operations"].items():
        for op in ops:
            if op["type"] == "ENTRY":
                cur[op["block_id"]] = op["bay_id"]
                ent[op["block_id"]] = int(t)
                place[op["block_id"]] = (int(op["orient_idx"]), float(op["x"]), float(op["y"]))
            else:
                ext[op["block_id"]] = int(t)
    v0 = [u[j] * sum(wl[b] for b in range(n) if cur[b] == j) for j in range(m)]
    TGT = v0.index(max(v0))
    z3 = sum(mxp[b] - pref[b][cur[b]] for b in range(n))
    print("\n=== %s  obj=%d  Z2=%s  Z3=%d   contested bay %d (%d residents)"
          % (MOD, int(o), c.get("obj2"), z3, TGT, sum(1 for b in range(n) if cur[b] == TGT)),
          flush=True)

    # [1] AREA over time in the contested bay
    W, H = int(bays[TGT]["width"]), int(bays[TGT]["height"])
    times = sorted({ent[b] for b in range(n)} | {ext[b] for b in range(n)})
    occ_at = []
    for t in times:
        live = [b for b in range(n) if cur[b] == TGT and ent[b] <= t < ext[b]]
        cells = set()
        for b in live:
            oi, px, py = place[b]
            for (k, x0, y0, x1, y1, _nl) in cells_of(b, oi):
                if k:
                    continue
                for xx in range(int(px + x0), int(px + x1)):
                    for yy in range(int(py + y0), int(py + y1)):
                        cells.add((xx, yy))
        occ_at.append(len(cells))
    peak = max(occ_at) if occ_at else 0
    mean = (sum(occ_at) / len(occ_at)) if occ_at else 0
    print("   [1] bay %dx%d = %d cells;  peak floor occupancy %d (%.0f%%),  mean %.0f (%.0f%%)"
          % (W, H, W * H, peak, 100.0 * peak / (W * H), mean, 100.0 * mean / (W * H)))

    # [2] ADMISSION -- the direct question, for every block not already in the bay
    E.clear_all()
    for q in range(n):
        oi, x, y = place[q]
        E.add(int(cur[q]), int(q), int(oi), float(x), float(y), int(ent[q]), int(ext[q]))
    adm, admn, adm_over, adm_flat = 0, 0, 0, 0
    n_over = n_flat = 0
    for b in range(n):
        if cur[b] == TGT:
            continue
        E.clear_all()
        for q in range(n):
            if q == b:
                continue
            oi, x, y = place[q]
            E.add(int(cur[q]), int(q), int(oi), float(x), float(y), int(ent[q]), int(ext[q]))
        k = len(E.feasible_scan(int(b), [int(TGT)], int(ent[b]), int(ext[b]), 1))
        adm += k
        admn += 1 if k else 0
        if over[b]:
            n_over += 1; adm_over += 1 if k else 0
        else:
            n_flat += 1; adm_flat += 1 if k else 0
    print("   [2] of %d outsiders, %d have at least one legal seat in bay %d at their own time"
          % (n - sum(1 for b in range(n) if cur[b] == TGT), admn, TGT))
    print("       total legal cells across all of them: %d  (mean %.1f per admitted block)"
          % (adm, adm / max(1, admn)))
    if n_over and n_flat:
        print("       overhanging blocks admitted %d/%d (%.0f%%),  straight prisms %d/%d (%.0f%%)"
              % (adm_over, n_over, 100.0 * adm_over / n_over,
                 adm_flat, n_flat, 100.0 * adm_flat / n_flat))

    # [3] HEIGHT MAP at the busiest instant
    tbusy = times[occ_at.index(peak)] if occ_at else 0
    hm = [[0] * W for _ in range(H)]
    for b in range(n):
        if cur[b] != TGT or not (ent[b] <= tbusy < ext[b]):
            continue
        oi, px, py = place[b]
        for (k, x0, y0, x1, y1, _nl) in cells_of(b, oi):
            for xx in range(int(px + x0), int(px + x1)):
                for yy in range(int(py + y0), int(py + y1)):
                    if 0 <= xx < W and 0 <= yy < H:
                        hm[yy][xx] = max(hm[yy][xx], k + 1)
    hist = {}
    for r in hm:
        for v in r:
            hist[v] = hist.get(v, 0) + 1
    # how isolated is the occupied set: free cells that touch an occupied one
    edge = sum(1 for y in range(H) for x in range(W) if hm[y][x] == 0
               and any(0 <= y + dy < H and 0 <= x + dx < W and hm[y + dy][x + dx]
                       for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))))
    print("   [3] at t=%d, per-cell stack height: %s" % (tbusy, dict(sorted(hist.items()))))
    print("       free cells adjacent to something occupied: %d  (perimeter per occupied cell"
          " %.2f -- higher means more scattered)" % (edge, edge / max(1, W * H - hist.get(0, 0))))
    rows[MOD] = (int(o), z3, peak, mean, admn, adm, edge)

print("\n=== SIDE BY SIDE")
print("   %-16s %9s %6s %8s %8s %8s %9s %7s" %
      ("module", "obj", "Z3", "peak", "mean", "admitted", "cells", "perim"))
for MOD in MODS:
    if MOD in rows:
        o, z3, peak, mean, admn, adm, edge = rows[MOD]
        print("   %-16s %9d %6d %8d %8.0f %8d %9d %7d"
              % (MOD, o, z3, peak, mean, admn, adm, edge))
if len(rows) == 2:
    a, b = (rows[MODS[0]], rows[MODS[1]])
    print("\n   the flatter solution is worth %+d objective and %+d Z3." % (b[0] - a[0], b[1] - a[1]))
    print("   it holds %+d peak cells and %+d mean cells -- %s"
          % (b[2] - a[2], b[3] - a[3],
             "so it is NOT simply emptier; the difference is arrangement"
             if abs(b[2] - a[2]) < 0.05 * a[2] else "it is measurably emptier, so part of the"
             " gain is that it declined work rather than packed better"))
    print("   and it admits %+d more outsiders over %+d more legal cells."
          % (b[4] - a[4], b[5] - a[5]))
    print("   -> %s"
          % ("admission tracks the objective, so the lever is genuinely 'how many blocks can"
             " still land', and a term that maximises THAT beats one that suppresses contact"
             if (b[4] - a[4]) * (a[0] - b[0]) > 0 else
             "admission does NOT track the objective here -- the gain came from somewhere else"
             " and the contact story is wrong"), flush=True)

"""How does cohort weighting actually buy Z1?

The objective says it wins; it does not say why.  Two mechanisms are plausible and they call
for different follow-up work, so they need separating:

  (A) co-departure.  A block nestled against a neighbour that leaves when it leaves frees a
      contiguous region at departure.  Nestled against a long-stayer, the same departure leaves
      a sliver bounded by something that will not move for a long time -- space that exists but
      cannot be entered.  If (A) is the mechanism, the free regions born at exit events get
      bigger and later blocks enter closer to their release.

  (B) shadow shrinkage.  Every block sterilises its whole UNION silhouette for the layer 0 of
      every later block, and union/layer0 measured 1.27x.  Blocks that share a window overlap
      their shadows in time instead of stacking them, so the same instantaneous occupancy costs
      less swept area.  If (B) is the mechanism, space-time utilisation rises without the free
      regions changing shape.

Both would show as "Z1 went down".  Only (A) says the next lever is departure scheduling; only
(B) says it is silhouette choice.  So measure, side by side, one beam with the weighting off and
one with it on:

  alignment   the contact the packing actually realised, weighted by how much the two windows
              overlap.  This is the sanity check -- if the scoring change did not move this, it
              did not do what it was written to do and the rest of the table is a coincidence.
  free        connected free components in the bay immediately after each exit event: how many,
              and how big the largest is.  (A) predicts fewer and bigger.
  st-util     occupied cell-time over bay cell-time, and the swept/instantaneous ratio.  (B)
              predicts this rises.
  delay       entry minus release, and how many blocks got in on their release date.  This is
              the channel Z1 has to come through either way.
"""
import json
import os
import sys
import time
from collections import defaultdict, deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_base as M          # noqa: E402  (has the cohort knob; cohort=0.0 is the plain arm)
from utils import Block         # noqa: E402  the grader's own geometry

PROB = int(sys.argv[1])
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
D = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
NB = len(D["blocks"])


def cells_of(bid, oi, x, y):
    """Union silhouette of a placed block as a set of integer cells."""
    from shapely.geometry import Polygon
    from shapely.prepared import prep
    b = Block(block_id=bid, block_data=D["blocks"][bid], x=x, y=y, orient_idx=oi)
    out = set()
    for poly in b.layers_at_pos():
        g = Polygon(poly)
        if not g.is_valid or g.area <= 0:
            continue
        pg = prep(g)
        x0, y0, x1, y1 = g.bounds
        for cx in range(int(x0), int(x1) + 1):
            for cy in range(int(y0), int(y1) + 1):
                if pg.contains(Polygon([(cx, cy), (cx + 1, cy), (cx + 1, cy + 1), (cx, cy + 1)]).centroid):
                    out.add((cx, cy))
    return out


def unpack(sol):
    """solution operations -> {bid: (bay, oi, x, y, entry, exit)}"""
    ent, ext = {}, {}
    for t, ops in sol["operations"].items():
        for op in ops:
            if op["type"] == "ENTRY":
                ent[op["block_id"]] = (op["bay_id"], op["orient_idx"], int(op["x"]), int(op["y"]), int(t))
            elif op["type"] == "EXIT":
                ext[op["block_id"]] = int(t)
    return {b: ent[b] + (ext[b],) for b in ent if b in ext}


def analyse(sol, label):
    rec = unpack(sol)
    cells = {b: cells_of(b, oi, x, y) for b, (bay, oi, x, y, en, ex) in rec.items()}
    owner = defaultdict(dict)                       # bay -> cell -> bid
    for b, (bay, oi, x, y, en, ex) in rec.items():
        for c in cells[b]:
            owner[bay][c] = b

    # -- alignment: realised contact, weighted by window overlap ------------------------------
    tot_ct = 0.0
    tot_al = 0.0
    for b, (bay, oi, x, y, en, ex) in rec.items():
        mylen = max(1, ex - en)
        for (cx, cy) in cells[b]:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                o = owner[bay].get((cx + dx, cy + dy))
                if o is None or o == b:
                    continue
                oen, oex = rec[o][4], rec[o][5]
                if not (en < oex and oen < ex):     # not co-resident: not contact at all
                    continue
                ov = min(ex, oex) - max(en, oen)
                den = min(mylen, max(1, oex - oen))
                tot_ct += 1.0
                tot_al += min(1.0, ov / den)
    align = tot_al / tot_ct if tot_ct else 0.0

    # -- free-region granularity right after each exit ----------------------------------------
    bays = {i: (int(bd["size"][0]), int(bd["size"][1])) if isinstance(bd.get("size"), (list, tuple))
            else (int(bd["width"]), int(bd["height"])) for i, bd in enumerate(D["bays"])}
    ncomp, biggest = [], []
    by_bay = defaultdict(list)
    for b, r in rec.items():
        by_bay[r[0]].append(b)
    for bay, blist in by_bay.items():
        W, H = bays[bay]
        exits = sorted({rec[b][5] for b in blist})
        for t in exits[:40]:                         # 40 events a bay is plenty for a mean
            occ = set()
            for b in blist:
                if rec[b][4] <= t < rec[b][5]:
                    occ |= cells[b]
            seen = set()
            comps = []
            for cx in range(W):
                for cy in range(H):
                    if (cx, cy) in occ or (cx, cy) in seen:
                        continue
                    q, sz = deque([(cx, cy)]), 0
                    seen.add((cx, cy))
                    while q:
                        ax, ay = q.popleft()
                        sz += 1
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            nx, ny = ax + dx, ay + dy
                            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in occ and (nx, ny) not in seen:
                                seen.add((nx, ny))
                                q.append((nx, ny))
                    comps.append(sz)
            if comps:
                ncomp.append(len(comps))
                biggest.append(max(comps))

    # -- space-time utilisation ---------------------------------------------------------------
    horizon = max(r[5] for r in rec.values())
    cellt = sum(len(cells[b]) * (rec[b][5] - rec[b][4]) for b in rec)
    baycellt = sum(W * H for (W, H) in bays.values()) * horizon
    # swept/instantaneous: union of silhouettes over a window vs mean instantaneous occupancy
    inst = []
    for t in range(0, horizon, max(1, horizon // 60)):
        a = 0
        for b, r in rec.items():
            if r[4] <= t < r[5]:
                a += len(cells[b])
        inst.append(a)
    mean_inst = sum(inst) / len(inst) if inst else 0.0

    # -- entry delay --------------------------------------------------------------------------
    rel = [D["blocks"][b]["release_time"] for b in range(NB)]
    delays = [rec[b][4] - rel[b] for b in rec]
    at_rel = sum(1 for d in delays if d <= 0)

    o, c = M._total(D, sol)
    print("  %-10s obj=%-11d Z1=%-8s Z2=%-6s Z3=%s" % (label, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3")))
    print("     alignment   %.4f   (contact-weighted window overlap of realised neighbours)" % align)
    print("     free        %.1f components, largest %.0f  (mean over exit events)"
          % (sum(ncomp) / len(ncomp) if ncomp else 0, sum(biggest) / len(biggest) if biggest else 0))
    print("     st-util     %.4f  (occupied cell-time / bay cell-time),  mean instantaneous %.0f cells"
          % (cellt / baycellt if baycellt else 0, mean_inst))
    print("     delay       mean %.1f, median %.0f, %d of %d entered at release"
          % (sum(delays) / len(delays), sorted(delays)[len(delays) // 2], at_rel, len(delays)))
    return dict(obj=o, align=align, ncomp=sum(ncomp) / len(ncomp) if ncomp else 0,
                big=sum(biggest) / len(biggest) if biggest else 0,
                stu=cellt / baycellt if baycellt else 0, delay=sum(delays) / len(delays), at_rel=at_rel)


CFG = dict(Bmul=1.0, K=4, pos_lam=0.12, order="defer_big", fut_beta=1.0, prefw=0.0, w3mul=3.0)
print("P%d  one beam each, %.0fs, identical axis but for the cohort floor" % (PROB, SECS))
res = {}
for coh in (0.0, 0.3):
    M._OGC_FAST_CACHE.clear()
    cfg = dict(CFG, cohort=coh)
    t = time.time()
    s = M._beam_once(D, SECS, cfg)
    if s is None:
        print("  cohort=%.1f -> beam produced nothing in %.0fs" % (coh, SECS))
        sys.exit(1)
    res[coh] = analyse(s, "cohort=%.1f" % coh)
    print("     (%.0fs)" % (time.time() - t))

a, b = res[0.0], res[0.3]
print("\n  delta (cohort on vs off)")
for k, name in (("obj", "objective"), ("align", "alignment"), ("ncomp", "free components"),
                ("big", "largest free"), ("stu", "space-time util"), ("delay", "mean entry delay"),
                ("at_rel", "entered at release")):
    if a[k]:
        print("     %-18s %+.2f%%" % (name, 100.0 * (b[k] - a[k]) / abs(a[k])))

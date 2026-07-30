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
  free        connected free components in the bay after each exit event, sampled across the
              whole horizon and skipping the first quarter.  (A) predicts fewer and bigger.
  shadow      union silhouette over layer 0, stay-weighted -- the 1.27x.  Orientation is a
              decision, so this moves.
  swept       union over one median stay divided by mean instantaneous occupancy -- the 1.6x,
              the pure cost of holding a cell for a whole stay.  (B) predicts this falls.
  delay       entry minus release, and how many blocks got in on their release date.  This is
              the channel Z1 has to come through either way.

Two metrics in the first cut of this file were wrong and are kept here as a warning.  "st-util"
divided occupied cell-time by bay cell-time: a block's stay IS its processing time and its area
does not depend on placement, so the numerator is an instance constant and the metric was
reporting 1/horizon.  And the free-region sample took exits[:40] -- the EARLIEST forty per bay,
which on P6 (~83 blocks a bay) is the fill phase, not the saturated phase where the tardiness is
made.  Both read as "no effect", which is exactly what a broken metric looks like.
"""
import json
import os
import sys
import time
from collections import defaultdict, deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import importlib               # noqa: E402
import myalg_base as M          # noqa: E402  scoring helpers only (_total); arms come from argv
from utils import Block         # noqa: E402  the grader's own geometry

PROB = int(sys.argv[1])
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
D = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
NB = len(D["blocks"])


def cells_of(bid, oi, x, y):
    """(union silhouette, layer-0 footprint) of a placed block, as sets of integer cells.

    Both are needed: the union is what sterilises space for every later block (check_entry
    forbids j >= k and everything rests on the floor), layer 0 is what the block actually
    needs.  Their ratio is the 1.27x overhang shadow.
    """
    from shapely.geometry import Polygon
    from shapely.prepared import prep
    b = Block(block_id=bid, block_data=D["blocks"][bid], x=x, y=y, orient_idx=oi)
    out, lay0 = set(), set()
    for li, poly in enumerate(b.layers_at_pos()):
        if li == 0:
            lay0 = set()
        g = Polygon(poly)
        if not g.is_valid or g.area <= 0:
            continue
        pg = prep(g)
        x0, y0, x1, y1 = g.bounds
        for cx in range(int(x0), int(x1) + 1):
            for cy in range(int(y0), int(y1) + 1):
                if pg.contains(Polygon([(cx, cy), (cx + 1, cy), (cx + 1, cy + 1), (cx, cy + 1)]).centroid):
                    out.add((cx, cy))
                    if li == 0:
                        lay0.add((cx, cy))
    return out, lay0


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
    both = {b: cells_of(b, oi, x, y) for b, (bay, oi, x, y, en, ex) in rec.items()}
    cells = {b: v[0] for b, v in both.items()}
    l0 = {b: (v[1] or v[0]) for b, v in both.items()}
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
    # The first cut of this took exits[:40], i.e. the EARLIEST forty per bay.  P6 puts ~83
    # blocks in a bay, so that sampled the fill phase -- when the yard still has unclaimed
    # room -- and never looked at the saturated phase where the tardiness is actually made.
    # Spread the sample over the whole horizon instead, and drop the first quarter.
    bays = {i: (int(bd["size"][0]), int(bd["size"][1])) if isinstance(bd.get("size"), (list, tuple))
            else (int(bd["width"]), int(bd["height"])) for i, bd in enumerate(D["bays"])}
    HZ = max(r[5] for r in rec.values())
    ncomp, biggest = [], []
    by_bay = defaultdict(list)
    for b, r in rec.items():
        by_bay[r[0]].append(b)
    for bay, blist in by_bay.items():
        W, H = bays[bay]
        exits = [t for t in sorted({rec[b][5] for b in blist}) if t >= 0.25 * HZ]
        for t in exits[::max(1, len(exits) // 40)]:
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

    # -- the two ratios that actually decompose the 49% ----------------------------------------
    # The first cut divided occupied cell-time by bay cell-time.  That is an instance constant:
    # a block's stay IS its processing time and its area does not depend on where it goes, so
    # the numerator cannot move and the metric was reporting 1/horizon.  The two ratios that DO
    # depend on the packing are the ones the 49% decomposes into:
    #
    #   shadow  union silhouette over layer 0, on the orientation the solver chose.  This is the
    #           1.27x, and orientation is a decision, so it moves.
    #   swept   over a window one median stay long, the union of everything that passed through
    #           divided by the mean instantaneous occupancy.  This is the 1.6x -- the pure cost
    #           of holding a cell for a whole stay -- and it is what (B) predicts cohort shrinks.
    shadow_n = shadow_d = 0.0
    for b, r in rec.items():
        stay = max(1, r[5] - r[4])
        shadow_n += len(cells[b]) * stay
        shadow_d += len(l0[b]) * stay
    shadow = shadow_n / shadow_d if shadow_d else 0.0

    medstay = sorted(max(1, r[5] - r[4]) for r in rec.values())[len(rec) // 2]
    sw_r = []
    for bay, blist in by_bay.items():
        for w0 in range(0, HZ - medstay, max(1, medstay)):
            w1 = w0 + medstay
            through = [b for b in blist if rec[b][4] < w1 and w0 < rec[b][5]]
            if not through:
                continue
            union = set()
            for b in through:
                union |= cells[b]
            inst = []
            for t in range(w0, w1, max(1, medstay // 8)):
                inst.append(sum(len(cells[b]) for b in through if rec[b][4] <= t < rec[b][5]))
            mi = sum(inst) / len(inst) if inst else 0.0
            if mi > 0:
                sw_r.append(len(union) / mi)
    swept = sum(sw_r) / len(sw_r) if sw_r else 0.0

    # -- entry delay --------------------------------------------------------------------------
    rel = [D["blocks"][b]["release_time"] for b in range(NB)]
    delays = [rec[b][4] - rel[b] for b in rec]
    at_rel = sum(1 for d in delays if d <= 0)

    o, c = M._total(D, sol)
    print("  %-10s obj=%-11d Z1=%-8s Z2=%-6s Z3=%s" % (label, int(o), c.get("obj1"), c.get("obj2"), c.get("obj3")))
    print("     alignment   %.4f   (contact-weighted window overlap of realised neighbours)" % align)
    print("     free        %.1f components, largest %.0f  (mean over exit events)"
          % (sum(ncomp) / len(ncomp) if ncomp else 0, sum(biggest) / len(biggest) if biggest else 0))
    print("     shadow      %.4f  (union / layer0, stay-weighted -- the 1.27x)" % shadow)
    print("     swept       %.4f  (union over one median stay / mean instantaneous -- the 1.6x)" % swept)
    print("     delay       mean %.1f, median %.0f, %d of %d entered at release"
          % (sum(delays) / len(delays), sorted(delays)[len(delays) // 2], at_rel, len(delays)))
    return dict(obj=o, align=align, ncomp=sum(ncomp) / len(ncomp) if ncomp else 0,
                big=sum(biggest) / len(biggest) if biggest else 0, shadow=shadow, swept=swept,
                delay=sum(delays) / len(delays), at_rel=at_rel)


MODS = sys.argv[3].split(",") if len(sys.argv) > 3 else ["myalg_orig", "myalgorithm"]
print("P%d  full pipeline, %.0fs each: %s" % (PROB, SECS, " vs ".join(MODS)))
res = {}
for name in MODS:
    mod = importlib.import_module(name)
    t = time.time()
    s = mod.algorithm(D, SECS)
    res[name] = analyse(s, name[:10])
    print("     (%.0fs)" % (time.time() - t))

a, b = res[MODS[0]], res[MODS[1]]
print("\n  delta (%s vs %s)" % (MODS[1], MODS[0]))
for k, nm in (("obj", "objective"), ("align", "alignment"), ("ncomp", "free components"),
              ("big", "largest free"), ("shadow", "shadow 1.27x"), ("swept", "swept 1.6x"),
              ("delay", "mean entry delay"), ("at_rel", "entered at release")):
    if a.get(k):
        print("     %-18s %+.2f%%" % (nm, 100.0 * (b[k] - a[k]) / abs(a[k])))

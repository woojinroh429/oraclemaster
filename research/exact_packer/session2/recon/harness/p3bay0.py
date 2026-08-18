"""Is bay 0 full, or is it just badly packed?

Everything measured on P3 says the same thing.  Z1 is 0, so the objective is a function of the
ASSIGNMENT alone; Z3 is 88% of it; every profitable move is a move into bay 0; and p3time found
23 of the 25 most valuable would-be entrants fit NOWHERE in their tardiness-free window.  The
conclusion drawn there -- "the wall is geometric" -- is right about the symptom and silent about
the cause, because every one of those checks held bay 0's existing residents at the exact
positions the pipeline gave them.  A block that cannot fit around a particular arrangement has
been told nothing about whether it could fit around a better one.

That matters here more than it usually would.  Bay 0's peak AREA occupancy is 54%: there is
half a bay of free cells, and what refuses the newcomers is not space but the crane's descent
rule -- a block may only land where the whole column above its footprint is clear of anything
resting at or above its own layer.  A layout can satisfy that rule for the blocks already in it
while fragmenting every column a newcomer would need, and greedy contact-maximising placement is
exactly the kind of procedure that would produce one.

So ask the question the earlier tests could not:

    take bay 0's residents AND the most valuable outsiders, free every position and every entry
    time, and let the exact packer seat as many as it can.

cranepack.pack is a maximum-weight set-packing search over (orientation, x, y, entry) columns
with the descent rule enforced pairwise -- it was built and validated against Gurobi earlier in
this project, reaching cardinality 10 on prob_20's binding bay.  Weights are the objective each
block is worth, so it maximises value seated, not count.

Three numbers come out, and they point at different work:

    residents re-seated   if this is below the incumbent's own count the packer is the weak
                          party, not the layout, and nothing below is trustworthy
    outsiders admitted    how many of the profitable moves a free repack can actually take
    value                 what that is worth in objective units

If outsiders admitted is 0, bay 0 is genuinely at its crane-rule capacity, the assignment bound
of 47,954 is unreachable, and the remaining work on P3 is Z2, not Z3.  If it is 5 or more, the
packing of one bay is worth more than every scoring knob tried this session put together.

    python3.12 harness/p3bay0.py [PROB] [SECONDS] [MOD] [PACK_SECONDS]
"""
import importlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as SC          # noqa: E402

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
MOD = sys.argv[3] if len(sys.argv) > 3 else "myalg_base"
TL = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0

import cranepack                 # noqa: E402
import numpy as np               # noqa: E402
from utils import Block          # noqa: E402

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
B, bays, w = d["blocks"], d["bays"], d["weights"]
n, m = len(B), len(bays)
w2, w3 = float(w["w2"]), float(w["w3"])
pref = [B[b]["bay_preferences"] for b in range(n)]
mxp = [max(pref[b]) for b in range(n)]
wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
pt = [int(B[b]["processing_time"]) for b in range(n)]
rel = [int(B[b]["release_time"]) for b in range(n)]
due = [int(B[b]["due_date"]) for b in range(n)]
bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]

sol = importlib.import_module(MOD).algorithm(d, SECS)
cur, ent, ext, place = [0] * n, {}, {}, {}
for t, ops in sol["operations"].items():
    for op in ops:
        if op["type"] == "ENTRY":
            cur[op["block_id"]] = op["bay_id"]
            ent[op["block_id"]] = int(t)
            place[op["block_id"]] = (int(op["orient_idx"]), float(op["x"]), float(op["y"]))
        else:
            ext[op["block_id"]] = int(t)


def obj_of(assign):
    load = [0.0] * m
    for b in range(n):
        load[assign[b]] += wl[b]
    v = [u[j] * load[j] for j in range(m)]
    z2 = math.floor(max(v) - min(v))
    z3 = sum(mxp[b] - pref[b][assign[b]] for b in range(n))
    return w2 * z2 + w3 * z3, z2, z3


base, z2, z3 = obj_of(cur)
v0 = [u[j] * sum(wl[b] for b in range(n) if cur[b] == j) for j in range(m)]
TGT = v0.index(max(v0))
res = [b for b in range(n) if cur[b] == TGT]
print("%s on P%d: obj=%d  Z2=%d  Z3=%d" % (MOD, PROB, int(base), z2, z3))
print("   contested bay %d: %.0fx%.0f, u=%.3f, %d residents"
      % (TGT, bays[TGT]["width"], bays[TGT]["height"], u[TGT], len(res)), flush=True)

# ---------------------------------------------------------------------------
# who wants in, and what each is worth.  Priced exactly: Z1 is 0, so moving block b to bay TGT
# changes the objective by a known amount and nothing else.
# ---------------------------------------------------------------------------
outs = []
for b in range(n):
    if cur[b] == TGT:
        continue
    alt = list(cur)
    alt[b] = TGT
    o, _, _ = obj_of(alt)
    if o < base:
        outs.append((base - o, b))
outs.sort(reverse=True)
NOUT = int(os.environ.get("NOUT", "40"))
outs = outs[:NOUT]
print("   %d outsiders would improve the objective by entering it; taking the %d best,"
      " worth %d in total if all were admitted"
      % (len([1 for b in range(n) if cur[b] != TGT]), len(outs), int(sum(g for g, _ in outs))),
      flush=True)

# ---------------------------------------------------------------------------
# hand the packer both groups with everything free
# ---------------------------------------------------------------------------
W, H = float(bays[TGT]["width"]), float(bays[TGT]["height"])
STEP = int(os.environ.get("STEP", "4"))
NENT = int(os.environ.get("NENT", "3"))       # entry times offered per block


def layers_and_bbox(bid):
    ol, ob = [], []
    for o in range(len(B[bid]["shape"])):
        blk = Block(block_id=bid, block_data=B[bid], x=0, y=0, orient_idx=o)
        ol.append([np.ascontiguousarray(np.asarray(L, dtype=np.float64))
                   for L in blk.layers_at_pos()])
        xs = [p[0] for L in blk.layers_at_pos() for p in L]
        ys = [p[1] for L in blk.layers_at_pos() for p in L]
        ob.append((float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))))
    return ol, ob


def windows(b, k):
    """k entry times spread over the tardiness-free window, so the packer may re-time as well
    as re-place.  A resident keeps its own time as one of the options."""
    lo, hi = rel[b], due[b] - pt[b]
    if hi < lo:
        return [(ent[b], ent[b] + pt[b])]
    ts = {lo, hi, ent[b] if lo <= ent[b] <= hi else lo}
    for i in range(k):
        ts.add(lo + (hi - lo) * i // max(1, k - 1))
    return [(t, t + pt[b]) for t in sorted(ts)]


cand = list(res) + [b for _, b in outs]
kind = ["res"] * len(res) + ["out"] * len(outs)
gainv = [0.0] * len(res) + [g for g, _ in outs]
blocks_in = []
for b in cand:
    ol, ob = layers_and_bbox(b)
    blocks_in.append((ol, ob, windows(b, NENT)))

# WEIGHTS.  A resident that is dropped loses its own preference and must go somewhere worse, so
# it is not free to evict -- it carries what it would cost.  An outsider carries what it gains.
# The packer then maximises the objective improvement rather than the block count, which is the
# only version of "seat as many as possible" that is not a trap: seating twenty worthless blocks
# while evicting five valuable ones would look like a win under cardinality.
wts = []
for i, b in enumerate(cand):
    if kind[i] == "res":
        alt = list(cur)
        alt[b] = min((j for j in range(m) if j != TGT), key=lambda j: pref[b][TGT] - pref[b][j])
        o, _, _ = obj_of(alt)
        wts.append(max(1.0, o - base))          # what dropping it would cost
    else:
        wts.append(gainv[i])

print("\n   packing %d blocks (%d residents + %d outsiders) into %.0fx%.0f, grid step %d,"
      " %d entry times each, %.0fs"
      % (len(cand), len(res), len(outs), W, H, STEP, NENT, TL), flush=True)

warm = [(i, place[b][0], int(place[b][1]), int(place[b][2]))
        for i, b in enumerate(cand) if kind[i] == "res"]
r = cranepack.pack(blocks_in, W, H, STEP, TL, seed=12345, warm=warm, frozen=[],
                   weights=[float(x) for x in wts])
got = {loc: (o, x, y, en, ex) for (loc, o, x, y, en, ex) in r[1]}

kept_res = [i for i in range(len(cand)) if kind[i] == "res" and i in got]
lost_res = [i for i in range(len(cand)) if kind[i] == "res" and i not in got]
adm = [i for i in range(len(cand)) if kind[i] == "out" and i in got]

print("\n[RESULT]")
print("   residents re-seated : %d of %d" % (len(kept_res), len(res)))
print("   outsiders admitted  : %d of %d" % (len(adm), len(outs)))
if adm:
    print("      %s" % ", ".join("blk %d (+%d)" % (cand[i], int(gainv[i])) for i in adm[:20]))
if lost_res:
    print("   residents displaced : %s" % ", ".join(str(cand[i]) for i in lost_res[:20]))

# net objective, pricing the displaced residents at their real next-best bay
newass = list(cur)
for i in adm:
    newass[cand[i]] = TGT
for i in lost_res:
    b = cand[i]
    newass[b] = min((j for j in range(m) if j != TGT), key=lambda j: pref[b][TGT] - pref[b][j])
no, nz2, nz3 = obj_of(newass)
print("\n   objective %d -> %d  (%+.2f%%),  Z2 %d -> %d,  Z3 %d -> %d"
      % (int(base), int(no), 100.0 * (no - base) / base, z2, nz2, z3, nz3))
if len(kept_res) < len(res) - len(lost_res):
    print("   NOTE: the packer could not even reproduce the incumbent's own residents --"
          " read the outsider count as a lower bound only")
print("   -> %s"
      % ("bay %d is at its crane-rule capacity: a free repack admits nothing, so the assignment"
         " bound is unreachable and what is left on P3 is Z2" % TGT if not adm else
         "bay %d was BADLY PACKED, not full: %d more blocks fit once the residents may move,"
         " worth %.2f%% of the objective" % (TGT, len(adm), 100.0 * (base - no) / base)),
      flush=True)

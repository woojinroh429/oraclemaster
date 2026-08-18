"""Is the target bay SATURATED?  The one measurement that would explain every null tonight.

THE CONTRADICTION THIS RESOLVES.  Two things are both measured and they do not sit together:

  the master reaches 36,759 -- the capacity-aware bound to six digits -- by moving 16 blocks
  INTO bay 0 and evicting nobody (masterprobe2, masterprobe3);

  every eviction-based route loses, because seating one outsider costs two or more residents
  and two evictions cost more than one admission gains (p3max measured eviction from bay 0 as
  needing gap/workload below 0.0948 against a cheapest resident of 0.145).

Only one reading satisfies both: bay 0 cannot physically hold its 55 residents plus the wished
blocks, so the master's assignment is reachable as an ASSIGNMENT and not as a PACKING.  I
reported the first without pressing the second hard enough, and if that is what is happening
then the bound is not an attainable target and every null tonight has a single cause.

THE TEST.  Hand cranepack the residents and the wished outsiders at UNIT weights and ask for
maximum cardinality -- the question it was validated against Gurobi on, with no objective
subtleties in the way.  Weights are all 1.0, so a block is a block:

    lands near |residents|      bay 0 is saturated; the wish is geometrically impossible and
                                the whole assignment direction closes on a measurement
    lands near |residents|+K    the room exists and the refusal is the search, not the bay

Run for several K so the answer is a curve rather than one point, and report which blocks were
dropped -- if the packer sheds residents to take outsiders at unit weight, cardinality is not
the binding thing either.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib

mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "myalg_brk")
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, "data/hidden/prob_3.json")))
sol = json.load(open("results/p3_incumbent.json"))
sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
n = len(d["blocks"]); m = len(d["bays"])
B = d["blocks"]; w = d["weights"]
o0, _ = mod._total(d, sol)

import bayrepack as R
import cranepack as CP

wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
pref = [B[b]["bay_preferences"] for b in range(n)]
mxp = [max(p) for p in pref]
pt = [int(B[b]["processing_time"]) for b in range(n)]
rel = [int(B[b]["release_time"]) for b in range(n)]
due = [int(B[b]["due_date"]) for b in range(n)]
bar = [float(d["bays"][j]["width"]) * float(d["bays"][j]["height"]) for j in range(m)]
u = [(sum(bar) / m) / bar[j] for j in range(m)]

cur = [-1] * n; ent = [-1] * n; ext = [-1] * n
for t, ops in sol["operations"].items():
    for op in ops:
        b = op["block_id"]
        if op["type"] == "ENTRY":
            cur[b] = op["bay_id"]; ent[b] = int(t)
        else:
            ext[b] = int(t)

want = R._wish(cur, wl, pref, mxp, u, m, n, 40, 5.0, float(w.get("w2", 0)), float(w["w3"]))
TGT = 0
wished = [b for b in range(n) if want[b] != cur[b] and want[b] == TGT]
res = [b for b in range(n) if cur[b] == TGT]
W, H = float(d["bays"][TGT]["width"]), float(d["bays"][TGT]["height"])
print("incumbent obj=%d   bay %d = %g x %g   residents %d   wished in %d"
      % (int(o0), TGT, W, H, len(res), len(wished)), flush=True)


def windows(b, nent):
    lo, hi = rel[b], due[b] - pt[b]
    if hi < lo:
        return [(ent[b], ent[b] + pt[b])]
    ts = {lo, hi}
    if lo <= ent[b] <= hi:
        ts.add(ent[b])
    for i in range(max(1, nent)):
        ts.add(lo + (hi - lo) * i // max(1, nent - 1) if nent > 1 else lo)
    return [(t, t + pt[b]) for t in sorted(ts)]


print("\n  %-4s %-9s %-9s %-9s %s" % ("K", "offered", "seated", "outs in", "residents dropped"))
for K in (0, 2, 4, 8, len(wished)):
    cand = list(res) + wished[:K]
    blocks_in = []
    for b in cand:
        ol, ob = R._layers_bbox(B, b)
        blocks_in.append((ol, ob, windows(b, 3)))
    warm = []
    for i, b in enumerate(cand):
        if i < len(res):
            for t, ops in sol["operations"].items():
                for op in ops:
                    if op["block_id"] == b and op["type"] == "ENTRY":
                        warm.append((i, int(op["orient_idx"]), int(op["x"]), int(op["y"])))
    t = time.time()
    r = CP.pack(blocks_in, W, H, 4, budget, seed=12345, warm=warm or None, frozen=[],
                weights=[1.0] * len(cand))       # UNIT weights: a block is a block
    got = {loc for (loc, o, x, y, en, ex) in r[1]}
    seated = len(got)
    outs_in = sum(1 for i in range(len(res), len(cand)) if i in got)
    dropped = [cand[i] for i in range(len(res)) if i not in got]
    print("  %-4d %-9d %-9d %-9d %s  [%.0fs]"
          % (K, len(cand), seated, outs_in,
             ("none" if not dropped else ",".join("b%d" % q for q in dropped[:10])),
             time.time() - t), flush=True)

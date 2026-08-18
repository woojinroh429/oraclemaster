"""Does the per-column-weight cranepack answer EXACTLY as the old one when no win_weights are
given?  If it does not, every measurement in results/ stops being comparable and the change has
to be reverted before anything else is tried.

Determinism comes from max_iters, not from the clock: pack() is time-budgeted and two runs of
the same binary at the same wall-clock budget need not agree, so a wall-clock A/B could not tell
a real difference from ordinary jitter.  With max_iters fixed and the seed fixed, the search
does the same number of steps in both binaries and the selection must match to the digit.
"""
import json, os, sys, hashlib
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, sys.argv[1])                      # the .so directory under test
import cranepack as CP                               # noqa: E402
import bayrepack as R                                # noqa: E402

prob = json.load(open(os.path.join(HERE, "data/stage2/prob_24.json")))
B = prob["blocks"]
cand = list(range(28))
blocks_in = [(R._layers_bbox(B, b)[0], R._layers_bbox(B, b)[1],
              [(int(B[b]["release_time"]), int(B[b]["release_time"]) + int(B[b]["processing_time"])),
               (int(B[b]["release_time"]) + 3,
                int(B[b]["release_time"]) + 3 + int(B[b]["processing_time"]))]) for b in cand]
W = float(prob["bays"][0]["width"]); H = float(prob["bays"][0]["height"])
wts = [1.0 + (b % 7) for b in cand]

kw = {}
if len(sys.argv) > 2 and sys.argv[2] == "win":
    # half the value if the block takes the later window -- a weighting the old binary has no
    # way to express, so this arm is expected to DIFFER and that is the point
    kw["win_weights"] = [[w, w * 0.5] for w in wts]
elif len(sys.argv) > 2 and sys.argv[2] == "bay1":
    # ONE bay named explicitly.  bays=[(W,H)] has to be the same problem as no bays at all: same
    # columns, same edges, same seats.  If it is not, the multi-bay path has changed the
    # single-bay answer and every earlier measurement stops being comparable.  win_weights is
    # indexed bay*n_entries + variant, which at one bay is the variant, so the SAME table is
    # passed here as in the "win" arm -- that identity is part of what is being checked.
    kw["win_weights"] = [[w, w * 0.5] for w in wts]
    kw["bays"] = [(W, H)]
elif len(sys.argv) > 2 and sys.argv[2] == "bay2":
    # TWO IDENTICAL BAYS, which is the cost measurement.  Cross-bay pairs cannot conflict, so a
    # second bay must double the column count and double the edge count -- not quadruple it.  The
    # seats are free to differ (there are two of everything now); n_cols and n_edges are the
    # numbers this arm exists to print.
    kw["win_weights"] = [[w, w * 0.5, w, w * 0.5] for w in wts]
    kw["bays"] = [(W, H), (W, H)]

r = CP.pack(blocks_in, W, H, 4, 30.0, seed=1, warm=None, frozen=[],
            weights=wts, total_s=60.0, max_iters=200000, **kw)
seat = sorted((int(l), int(o), int(x), int(y), int(e), int(x2)) for (l, o, x, y, e, x2, *_b) in r[1])
print("seated %d/%d  digest %s" % (len(seat), len(cand),
                                   hashlib.sha1(repr(seat).encode()).hexdigest()[:16]))
print("late-window seats: %d" % sum(1 for s in seat
                                    if s[4] != int(B[cand[s[0]]]["release_time"])))
print("ncol %d  nedge %d  build %.2fs" % (int(r[2]), int(r[3]), float(r[4]) / 1000.0))
if r[1] and len(r[1][0]) > 6:
    _byb = {}
    for p in r[1]:
        _byb[int(p[6])] = _byb.get(int(p[6]), 0) + 1
    print("seats per bay: %s" % sorted(_byb.items()))

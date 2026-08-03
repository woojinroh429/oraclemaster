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

r = CP.pack(blocks_in, W, H, 4, 30.0, seed=1, warm=None, frozen=[],
            weights=wts, total_s=60.0, max_iters=200000, **kw)
seat = sorted((int(l), int(o), int(x), int(y), int(e), int(x2)) for (l, o, x, y, e, x2) in r[1])
print("seated %d/%d  digest %s" % (len(seat), len(cand),
                                   hashlib.sha1(repr(seat).encode()).hexdigest()[:16]))
print("late-window seats: %d" % sum(1 for s in seat
                                    if s[4] != int(B[cand[s[0]]]["release_time"])))

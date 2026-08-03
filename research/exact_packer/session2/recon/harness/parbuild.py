"""Does the parallel conflict-graph build produce the SAME graph, and how much faster?

n_edges is the invariant.  adj is sorted after the merge so insertion order cannot matter, and a
private per-thread memo can only lose reuse, never change a predicate -- a miss recomputes the
same answer.  If the edge count moves at all, the parallel build is solving a different problem
and it does not ship, which is the same bar the conflict memo's 36-edge disagreement was held to.

Timing is the BUILD only, taken from what pack() already returns (build_ms), not from the wall
clock around the call: the search that follows runs for as long as it is asked and would swamp it.
"""
import json, os, sys, time
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, H); sys.path.insert(0, sys.argv[1])
import cranepack as CP                                    # noqa: E402
import bayrepack as R                                     # noqa: E402

prob = json.load(open(os.path.join(H, 'data/stage2/prob_%s.json' % (sys.argv[2] if len(sys.argv) > 2 else '13'))))
B = prob["blocks"]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 40
cand = list(range(N))
blocks_in = [(R._layers_bbox(B, b)[0], R._layers_bbox(B, b)[1],
              [(int(B[b]["release_time"]) + k, int(B[b]["release_time"]) + k + int(B[b]["processing_time"]))
               for k in (0, 2, 4)]) for b in cand]
W = float(prob["bays"][0]["width"]); H2 = float(prob["bays"][0]["height"])
t = time.time()
r = CP.pack(blocks_in, W, H2, 4, 1.0, seed=1, warm=None, frozen=[],
            weights=[1.0] * len(cand), total_s=600.0, max_iters=1)
el = time.time() - t
print("ncol=%-7d n_edges=%-10d build=%.2fs  total=%.2fs  aborted=%s"
      % (r[2], r[3], float(r[4]) / 1000.0, el, r[9]))

"""Where does a run actually spend its time?  Measured, for the first time, outside cranepack.

EVERY OPTIMISATION TODAY WAS AIMED AT THE ONE COMPONENT THAT HAD EVER BEEN PROFILED.  cranepack's
build went 10.5x faster, which is real, but it was chosen because it was the part I had looked
at -- not because anything said it dominated the run.  Twice I then guessed at where the time
went INSIDE it and was wrong both times: the free-column bitset assumed greedy_extend's scan
dominated the search and came out 1.6x SLOWER, and the conflict memo's 36-edge disagreement was
blamed on key aliasing before the actual cause turned out to be floating point.

So this measures instead.  Three things, none of which has a number today:

    _total          the only selection criterion in the pipeline, and it re-runs the REAL grader
                    (check_feasibility) on every solution that beats the incumbent.  The grader
                    is a correctness tool, not a fast one, and nothing has ever counted the calls
                    or the seconds.
    the operators   beam, grow, bal, bay, brk -- the loop already tracks spent[] per operator for
                    its own scheduling, and that array is exactly the breakdown, never reported.
    cranepack       build and search separately, from the (build_ms, solve_ms) it already returns,
                    so the 10.5x can be put next to the run total instead of standing alone.

Method: wrap, do not sample.  A sampling profiler would attribute C++ time to whatever Python
frame happened to be on the stack, and most of the work here is inside .so calls.  Wrapping the
handful of boundaries gives exact seconds and exact call counts, and costs a few microseconds
per call against runs measured in minutes.

Run: python3.12 harness/wheretime.py <prob> <secs>
"""
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
# one worker: the point is the shape of the time, and four workers racing each other on four
# cores would report wall time that is mostly contention
os.environ["WORKERS"] = "1"

import myalgorithm as A                                  # noqa: E402
import bayrepack as R                                    # noqa: E402
import utils                                             # noqa: E402

T = collections.Counter()
N = collections.Counter()


def wrap(mod, name, label):
    fn = getattr(mod, name, None)
    if fn is None:
        return False

    def w(*a, **k):
        t = time.time()
        try:
            return fn(*a, **k)
        finally:
            T[label] += time.time() - t
            N[label] += 1
    setattr(mod, name, w)
    return True


# the real grader, wherever it is reached from
for m in (utils, A):
    wrap(m, "check_feasibility", "check_feasibility (the real grader)")
wrap(A, "_fast_obj", "_fast_obj (arithmetic screen)")
wrap(A, "_build_operations", "_build_operations")
wrap(A, "_assign", "bay assign (CP-SAT)")
wrap(A, "_balance", "balance")
wrap(A, "_contact_beam", "contact_beam (construction)")
wrap(A, "_regrow", "regrow")
wrap(R, "repack", "brk repack (whole operator)")

# cranepack reports its own split, so take it from the result rather than timing around it
import cranepack as CP                                   # noqa: E402
_pack = CP.pack


def packw(*a, **k):
    t = time.time()
    r = _pack(*a, **k)
    el = time.time() - t
    b = float(r[4]) / 1000.0
    T["  ...cranepack build"] += b
    T["  ...cranepack search"] += max(0.0, el - b)
    N["  ...cranepack build"] += 1
    return r


CP.pack = packw
R.CP = CP

# --data <dir> so the final-round practice instances can be profiled; the preliminary
# hidden set stays the default, which keeps every earlier log in this directory readable.
_DD = "data/hidden"
if "--data" in sys.argv:
    _DD = sys.argv[sys.argv.index("--data") + 1]
d = json.load(open(os.path.join(HERE, _DD, "prob_%d.json" % PROB)))
t0 = time.time()
sol = A.algorithm(d, SECS)
wall = time.time() - t0
c = utils.check_feasibility(d, sol)

print("\nP%d  %.0fs budget, ONE worker   obj=%.0f  feas=%s  wall=%.1fs"
      % (PROB, SECS, c["objective"], c["feasible"], wall))
print("  %-38s %9s %8s %7s" % ("component", "seconds", "calls", "% wall"))
for k, v in sorted(T.items(), key=lambda kv: -kv[1]):
    print("  %-38s %9.1f %8d %6.1f%%" % (k, v, N[k], 100.0 * v / max(1e-9, wall)))
print("\n  NOTE: components nest -- brk repack contains cranepack, and the operators contain")
print("  _total.  Read each line against the wall clock, not against each other.")

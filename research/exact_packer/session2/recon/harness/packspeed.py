"""Is the fast conflict-graph build the SAME graph, and how much faster?

The build is the uninterruptible half of a pack -- the search honours its deadline, the build
cannot -- so it is what decides which tier the operator can afford, and the tier is worth real
objective (nent 3 -> 6 took P3 from 88,695 to 80,795).  It was one thread out of four, visiting
all ncol*(ncol-1)/2 pairs and rejecting most on the time test.

Two changes, neither of which may alter the edge set:

    SWEEP    visit columns in ENTRY order, so once cb.entry >= ca.exit no later b can overlap
             and the inner loop BREAKS.  P3's processing times are 3/7/12 against a horizon of
             82, so two columns share time about 17% of the time.
    THREADS  per-thread edge buffers, adj filled serially afterwards, schedule(dynamic).

CRANEPACK_SLOW=1 restores the original loop, so this compares them directly rather than
asserting they agree.  n_cols and n_edges come straight out of pack()'s return tuple, and the
placement is compared element by element -- a graph that differs by one edge can still produce
the same count, so the count alone would not be evidence.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASES = [("prob_3", 0, 4, 40, 3), ("prob_3", 0, 4, 40, 6), ("prob_3", 0, 3, 40, 3)]

CHILD = r'''
import json, os, sys, time
sys.path.insert(0, %r)
import myalg_brk as A, bayrepack as R, cranepack as CP
d = json.load(open(os.path.join(%r, "data/hidden/%s.json")))
sol = json.load(open(os.path.join(%r, "results/p3_incumbent.json")))
sol["operations"] = {int(k): v for k, v in sol["operations"].items()}
os.environ["BRK_STEP"], os.environ["BRK_NOUT"], os.environ["BRK_NENT"] = "%d", "%d", "%d"
_orig = CP.pack
_seen = []
def _spy(*a, **k):
    t = time.time(); r = _orig(*a, **k); el = time.time() - t
    _seen.append((r[2], r[3], float(r[4]), el, sorted(r[1])))
    return r
CP.pack = _spy
R.repack(d, sol, 12.0, A._total, A._build_operations, A._ogc_fast_engine, hard=1e9)
if not _seen:
    print("NOCALL")
else:
    ncol, nedge, bms, el, place = _seen[0]
    print(json.dumps({"ncol": ncol, "nedge": nedge, "build_s": bms / 1000.0,
                      "total_s": el, "place": place}))
'''


def run(case, slow):
    prob, _bay, st, no, ne = case
    src = CHILD % (HERE, HERE, prob, HERE, st, no, ne)
    env = dict(os.environ)
    env["CRANEPACK_SLOW"] = "1" if slow else "0"
    env["BRK_STEP"], env["BRK_NOUT"], env["BRK_NENT"] = str(st), str(no), str(ne)
    out = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True,
                         env=env, cwd=HERE, timeout=3600)
    line = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    if not line or line == "NOCALL":
        return None
    return json.loads(line)


print("  %-22s %-9s %-9s %-9s %-9s %s"
      % ("case", "ncol", "edges", "build", "speedup", "placement"))
for c in CASES:
    tag = "%s step=%d nout=%d nent=%d" % (c[0], c[2], c[3], c[4])
    a = run(c, slow=True)
    b = run(c, slow=False)
    if a is None or b is None:
        print("  %-22s no pack call" % tag)
        continue
    same_graph = (a["ncol"] == b["ncol"] and a["nedge"] == b["nedge"])
    same_place = (a["place"] == b["place"])
    verdict = ("IDENTICAL" if same_graph and same_place
               else ("edges differ" if not same_graph else "same graph, different placement"))
    print("  %-22s %-9d %-9d %-9.1f %-9s %s"
          % (tag, b["ncol"], b["nedge"], b["build_s"],
             "%.1fx" % (a["build_s"] / max(1e-9, b["build_s"])), verdict))
    print("       slow: build %.1fs  edges %d       fast: build %.1fs  edges %d"
          % (a["build_s"], a["nedge"], b["build_s"], b["nedge"]))

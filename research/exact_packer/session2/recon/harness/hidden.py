"""Paired A/B on the ACTUAL hidden instances, each at its own published time limit.

Everything before this measured stand-ins from the training set at a uniform 60s.  These are
the six problems that get scored, and their limits run 60s to 900s, so this is the only
comparison that speaks directly to the result.

    python3.12 harness/hidden.py [probs] [--v2-only]

probs defaults to 1,2,3,4,5,6.  Runs the shipped pipeline and myalg_v2 back to back in one
process so both see the same machine load.
"""
import sys, os, json, time, importlib

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
sys.path.insert(0, REC); os.chdir(REC)
import utils

# published limits, one per problem
LIMIT = {1: 60, 2: 120, 3: 240, 4: 480, 5: 600, 6: 900}
DIRS = ("data/hidden", "/tmp/ds/hidden", "/tmp/hidden")


def load(p):
    for d in DIRS:
        c = os.path.join(d, "prob_%d.json" % p)
        if os.path.exists(c):
            return json.load(open(c))
    raise SystemExit("prob_%d.json not found in %s" % (p, DIRS))


probs = [int(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 and
                          not sys.argv[1].startswith("--") else "1,2,3,4,5,6".split(","))]
v2_only = "--v2-only" in sys.argv

arms = [("V2", importlib.import_module("myalg_v2"))]
if not v2_only:
    arms.insert(0, ("OLD", importlib.import_module("myalgorithm")))
for _, M in arms:
    M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST

w = l = t = 0
for p in probs:
    d = load(p)
    T = LIMIT[p]
    row = {}
    for tag, M in arms:
        t0 = time.time()
        s = M.algorithm(d, timelimit=T)
        c = utils.check_feasibility(d, s)
        row[tag] = (int(c["objective"]) if c.get("feasible") else -1,
                    c.get("obj1"), c.get("obj2"), c.get("obj3"), time.time() - t0)
        print("  P%d %-4s %4ds  obj=%-11d Z1=%-8s Z2=%-6s Z3=%-8s  ran %.0fs"
              % (p, tag, T, row[tag][0], row[tag][1], row[tag][2], row[tag][3],
                 row[tag][4]), flush=True)
    if len(arms) == 2:
        a, b = row["OLD"], row["V2"]
        g = (100.0 * (b[0] - a[0]) / a[0]) if (a[0] > 0 and b[0] > 0) else float("nan")
        if g < -0.05: w += 1
        elif g > 0.05: l += 1
        else: t += 1
        print("  P%d  ->  %+.2f%%\n" % (p, g), flush=True)
if len(arms) == 2:
    print("TOTAL v2 wins %d losses %d ties %d" % (w, l, t), flush=True)

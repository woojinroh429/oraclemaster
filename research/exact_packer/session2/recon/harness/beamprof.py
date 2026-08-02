"""Inside the beam: where do contact_beam's 105 s and regrow's 35 s actually go?

The whole-run profile put the beam at 43.9% and regrow at 14.8% -- 58.7% together, both the same
code -- against cranepack's build at 4.9% after this afternoon's 10.5x.  So the beam is now the
run, and nothing inside it has ever been read.

NOTHING NEW IS BUILT HERE.  ogc_fast.cpp already counts every phase and already exposes the
counters through pybind; OGC_CBPROF=1 arms them.  They have simply never been printed.  That is
worth saying plainly: the instrumentation for the biggest component of the run was sitting in
the binary, complete, unused.

    cb_t_rebuild   rebuilding the occupancy state between beam expansions
    cb_t_scan      the first-choice position scan
    cb_t_retry     rescans over later entry times when the first choice finds nothing -- the
                   comment in the engine says this path was invisible until it was counted
    cb_t_roll      per-state completion rollouts
    cb_t_exact     exact placement_feasible_tl calls, the expensive geometric test
    cb_n_cell      cells visited, cb_n_bitmap / cb_n_exact how they were resolved
    cb_n_arskip    area-precheck skips, cb_n_arbad how many of those were wrong

READ THE COUNTS AS WELL AS THE SECONDS.  cb_n_exact against cb_n_cell says what fraction of
cells needed the exact test, and that ratio is what any optimisation here has to move.  Counting
first is the whole point: the free-column bitset was built on an assumption about which line was
hot, and came out 1.6x SLOWER.

One worker, because four racing over four cores measures contention, not shape.

Run: python3.12 harness/beamprof.py <prob> <secs>
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

PROB = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
os.environ["WORKERS"] = "1"
os.environ["OGC_CBPROF"] = "1"

import myalgorithm as A                                  # noqa: E402
import utils                                             # noqa: E402

FIELDS = ["cb_t_rebuild", "cb_t_scan", "cb_t_retry", "cb_t_roll", "cb_t_exact"]
COUNTS = ["cb_n_scan", "cb_n_cell", "cb_n_ok", "cb_n_after", "cb_n_bitmap",
          "cb_n_exact", "cb_n_hard", "cb_n_corner", "cb_n_sweep", "cb_n_both",
          "cb_n_retry", "cb_n_arskip", "cb_n_arbad", "cb_n_badrej"]
TOT = {k: 0.0 for k in FIELDS + COUNTS}
BEAM = [0.0, 0]


class Proxy(object):
    """ogc_fast.Engine is a pybind class and refuses attribute assignment, so the counters have
    to be harvested through a wrapper the factory hands out instead of by patching the object.
    Everything except contact_beam passes straight through untouched.

    Harvesting per CALL is not optional: contact_beam zeroes its counters on entry, so reading
    them once at the end would report only the last invocation of the run."""

    def __init__(self, e):
        object.__setattr__(self, "_e", e)

    def __getattr__(self, k):
        if k == "contact_beam":
            e = object.__getattribute__(self, "_e")

            def w(*a, **kw):
                t = time.time()
                r = e.contact_beam(*a, **kw)
                BEAM[0] += time.time() - t
                BEAM[1] += 1
                for f in FIELDS + COUNTS:
                    TOT[f] += float(getattr(e, f, 0.0) or 0.0)
                return r
            return w
        return getattr(object.__getattribute__(self, "_e"), k)


_factory = A._ogc_fast_engine
A._ogc_fast_engine = lambda prob: Proxy(_factory(prob))

d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % PROB)))
t0 = time.time()
sol = A.algorithm(d, SECS)
wall = time.time() - t0
c = utils.check_feasibility(d, sol)

print("\nP%d  %.0fs, ONE worker   obj=%.0f  feas=%s  wall=%.1fs   beam wall=%.1fs over %d calls"
      % (PROB, SECS, c["objective"], c["feasible"], wall, BEAM[0], BEAM[1]))
acc = sum(TOT[f] for f in FIELDS)
print("  %-16s %9s %8s" % ("phase", "seconds", "% wall"))
for f in sorted(FIELDS, key=lambda x: -TOT[x]):
    print("  %-16s %9.1f %7.1f%%" % (f, TOT[f], 100.0 * TOT[f] / max(1e-9, wall)))
print("  %-16s %9.1f %7.1f%%   (beam wall %.1f s -- the rest is the loop itself)"
      % ("accounted", acc, 100.0 * acc / max(1e-9, wall), BEAM[0]))
print()
print("  %-16s %14s" % ("count", "value"))
for f in COUNTS:
    print("  %-16s %14.0f" % (f, TOT[f]))
if TOT["cb_n_cell"] > 0:
    print("\n  exact tests per cell visited: %.4f   (bitmap resolved: %.4f)"
          % (TOT["cb_n_exact"] / TOT["cb_n_cell"], TOT["cb_n_bitmap"] / TOT["cb_n_cell"]))
if TOT["cb_n_cell"] > 0:
    print("  cells that survive feasibility and get scored: %.2f%%"
          % (100.0 * TOT["cb_n_ok"] / TOT["cb_n_cell"]))
    print("  cells scored AFTER the best was found: %.0f of %.0f (%.1f%%) -- the early-exit prize"
          % (TOT["cb_n_after"], TOT["cb_n_ok"],
             100.0 * TOT["cb_n_after"] / max(1.0, TOT["cb_n_ok"])))
_paths = TOT["cb_n_corner"] + TOT["cb_n_sweep"] + TOT["cb_n_both"]
if _paths > 0:
    print("  candidate set per (block,bay,orient): corner only %.1f%%, full sweep %.1f%%,"
          " BOTH %.1f%%"
          % (100.0 * TOT["cb_n_corner"] / _paths, 100.0 * TOT["cb_n_sweep"] / _paths,
             100.0 * TOT["cb_n_both"] / _paths))
if TOT["cb_n_scan"] > 0:
    print("  %.0f scans, %.0f cells each on average" % (TOT["cb_n_scan"],
                                                        TOT["cb_n_cell"] / TOT["cb_n_scan"]))
if TOT["cb_n_arskip"] > 0:
    print("  area precheck: %.0f skips, %.0f of them wrong (%.2g)"
          % (TOT["cb_n_arskip"], TOT["cb_n_arbad"],
             TOT["cb_n_arbad"] / max(1.0, TOT["cb_n_arskip"])))

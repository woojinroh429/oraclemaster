"""What is the repacking operator's column count actually made of?

Columns are generated as (block, orient, x, y) x (entry window).  Every column inside one of those
groups has identical geometry and differs only in its time window, so the exact crane test is
shared across the group by the memo -- but the EDGES are not.  A conflicting geometric pair is
stored once for every (ei_A, ei_B) whose windows overlap, which puts a multiplicative factor on
the edge count that the pair enumeration does not carry.

That factor decides whether storing conflicts at the geometry level is worth the rework, and it is
measurable rather than arguable: CRANEPACK_COLSTAT=1 prints ncol against the number of distinct
geometric slots.  Ratio near 1 and there is nothing to win; 3 to 5 and the edge count -- and the
gigabyte of adjacency that comes with it -- fall by that factor.

Driving the operator through the scheduler does not reliably reach it (a 90 s single-worker run on
prob_13 never called it once), so this calls repack() directly on a finished solution.

    usage:  CRANEPACK_COLSTAT=1 python3.12 harness/colstat.py <prob_id> [solve_s] [repack_s]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalgorithm as M          # noqa: E402
import bayrepack                 # noqa: E402
import utils                     # noqa: E402


def main():
    pid = sys.argv[1]
    solve_s = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    repack_s = float(sys.argv[3]) if len(sys.argv) > 3 else 45.0
    d = json.load(open("data/stage2/prob_%s.json" % pid))

    sol = M.algorithm(d, solve_s)
    base = utils.check_feasibility(d, sol)
    print("P%-3s solved %.0fs  obj=%.0f" % (pid, solve_s, base["objective"]), flush=True)

    # repack() wants the caller's own scorer and builder, which is how the module avoids deciding
    # what "better" means; myalgorithm already has both.
    try:
        out = bayrepack.repack(d, sol, repack_s, M._total, M._build_operations,
                               engine_fn=getattr(M, "_ogc_fast_engine", None), hard=repack_s)
    except Exception as e:
        print("P%-3s repack raised %r" % (pid, e))
        return
    if out is None:
        print("P%-3s repack returned nothing" % pid)
        return
    got = utils.check_feasibility(d, out)
    print("P%-3s repack -> obj=%.0f (%+.2f%%) feas=%s"
          % (pid, got["objective"],
             100.0 * (got["objective"] - base["objective"]) / max(1.0, base["objective"]),
             got["feasible"]))


if __name__ == "__main__":
    main()

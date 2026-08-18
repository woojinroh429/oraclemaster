"""How much tardiness is still reachable in a finished solution?

The premise for spending the reserved tail on Z1 was that Z1 carries a median 59% of the objective
and 92% of the run-to-run variance (results/audit/rep722.md, wstat.md).  The premise's own
codebase disagrees: myalgorithm.py records _pull_early as measured at 0.05% for 22 s and
deliberately unregistered.

That measurement was taken inside the operator loop, where the pass competes for budget and is
handed whatever slice the scheduler spares.  The tail is a different setting -- it runs once, on
the final solution, with a guaranteed share and nothing else competing.  Before testing a policy,
measure the opportunity: solve normally, then hand the finished solution to _pull_early with the
tail's own budget and report what it recovers.

One run per instance answers it.  If the recovery is near zero the policy experiment is not worth
running at all; if it is real, the A/B is worth the hour.

    usage:  python3.12 harness/z1probe.py <prob_id> [budget] [tail]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalgorithm as M          # noqa: E402
import utils                     # noqa: E402


def main():
    pid = sys.argv[1]
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 180.0
    tail = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
    d = json.load(open("data/stage2/prob_%s.json" % pid))

    t0 = time.time()
    sol = M.algorithm(d, budget)
    solve_s = time.time() - t0
    base = utils.check_feasibility(d, sol)

    t1 = time.time()
    try:
        imp = M._pull_early(d, sol, tail)
    except Exception as e:                       # a probe must not die on the operator
        print("P%-3s PULL RAISED %r" % (pid, e))
        return
    pull_s = time.time() - t1

    if imp is None:
        print("P%-3s %5.0fs obj=%-12.0f Z1=%-9.0f  pull returned nothing in %.0fs"
              % (pid, budget, base["objective"], base["obj1"], pull_s))
        return

    got = utils.check_feasibility(d, imp)
    # The tail may only ever be applied if it is both feasible and better on the FULL objective;
    # report what the caller would actually keep, not what the operator hoped for.
    kept = got["feasible"] and got["objective"] < base["objective"]
    print("P%-3s %5.0fs obj=%-12.0f -> %-12.0f (%+.2f%%)  Z1 %-9.0f -> %-9.0f (%+.2f%%)  "
          "Z3 %-8.0f -> %-8.0f  feas=%s keep=%s  pull %.0fs (solve %.0fs)"
          % (pid, budget, base["objective"], got["objective"],
             100.0 * (got["objective"] - base["objective"]) / max(1.0, base["objective"]),
             base["obj1"], got["obj1"],
             100.0 * (got["obj1"] - base["obj1"]) / max(1.0, base["obj1"]),
             base["obj3"], got["obj3"], got["feasible"], kept, pull_s, solve_s))


if __name__ == "__main__":
    main()

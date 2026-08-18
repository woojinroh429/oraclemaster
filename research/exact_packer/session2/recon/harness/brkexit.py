"""Where does the repacking operator actually stop?

It has seven exits and they all look like None to the caller.  Three instances traced by hand all
died at the same one -- a displaced block that could not be re-seated -- and in each case the
packer had already found an arrangement it liked.  That is the difference between an operator that
cannot find anything and one that finds something and throws it away, and the two want completely
different work.

Three instances is an anecdote.  This runs the operator to exhaustion on a set of them and counts
which exit fires, so the next thing built is aimed at the exit that costs the most.

Counted per call:

    declined        the cost model refused every configuration before packing
    aborted         the build ran out of time and was discarded
    no-entrant      no bay has a block that would profit by entering it
    no-move         the packer seated things but moved nothing between bays
    rehome-fail     a displaced block could not be re-seated ANYWHERE  <- the one in question
    incomplete      the rebuild did not account for every block
    reject          a complete, legal solution that did not beat the incumbent
    KEEP            an improvement, returned

`rehome-fail` and `reject` are the two that mean the search worked.  `reject` is honest failure --
the arrangement was legal and simply worse.  `rehome-fail` is a legal arrangement lost to
bookkeeping, and it is the only exit where the operator's own effort is provably wasted.

    usage:  python3.12 harness/brkexit.py <solve_s> <repack_s> <calls> <inst...>
"""
import io
import json
import os
import re
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalgorithm as M          # noqa: E402
import bayrepack                 # noqa: E402
import utils                     # noqa: E402

EXITS = ["declined", "aborted", "no-entrant", "no-move", "rehome-fail", "incomplete",
         "reject", "KEEP"]


def classify(trace):
    """Which exit the trace describes.  Ordered most specific first: a call that reaches the
    rehoming step has already passed the cost model and the packer."""
    if "could not be rehomed" in trace:
        return "rehome-fail"
    if "-> KEEP" in trace:
        return "KEEP"
    if "-> reject" in trace:
        return "reject"
    if "rebuilt" in trace and "of" in trace:
        return "incomplete"
    if "moved NO block" in trace:
        return "no-move"
    if "BUILD ABORTED" in trace:
        return "aborted"
    if "declined" in trace:
        return "declined"
    if "no bay has a profitable entrant" in trace or "no profitable entrant" in trace:
        return "no-entrant"
    return "other"


def main():
    solve_s = float(sys.argv[1])
    repack_s = float(sys.argv[2])
    calls = int(sys.argv[3])
    insts = sys.argv[4:]
    os.environ["BRK_DEBUG"] = "1"

    tally = {e: 0 for e in EXITS}
    tally["other"] = 0
    displaced_tot, displaced_lost = 0, 0

    for pid in insts:
        d = json.load(open("data/stage2/prob_%s.json" % pid))
        sol = M.algorithm(d, solve_s)
        base = utils.check_feasibility(d, sol)["objective"]
        cur, per = sol, []
        for _ in range(calls):
            buf = io.StringIO()
            with redirect_stdout(buf):
                out = bayrepack.repack(d, cur, repack_s, M._total, M._build_operations,
                                       engine_fn=getattr(M, "_ogc_fast_engine", None),
                                       hard=repack_s)
            tr = buf.getvalue()
            e = classify(tr)
            tally[e] = tally.get(e, 0) + 1
            per.append(e)
            # how much of the operator's own work the rehoming step discards
            m = re.search(r"displaced (\d+):", tr)
            if m:
                displaced_tot += int(m.group(1))
                if e == "rehome-fail":
                    displaced_lost += int(m.group(1))
            if out is not None:
                chk = utils.check_feasibility(d, out)
                if chk["feasible"]:
                    cur = out
        got = utils.check_feasibility(d, cur)["objective"]
        print("P%-3s %8.0f -> %8.0f (%+.2f%%)   %s"
              % (pid, base, got, 100.0 * (got - base) / max(1.0, base), " ".join(per)),
              flush=True)

    print("\n--- exits over %d calls ---" % sum(tally.values()))
    for e in EXITS + ["other"]:
        if tally.get(e):
            print("  %-12s %3d" % (e, tally[e]))
    if displaced_tot:
        print("  displaced blocks: %d seen, %d in calls that were then discarded (%.0f%%)"
              % (displaced_tot, displaced_lost, 100.0 * displaced_lost / displaced_tot))


if __name__ == "__main__":
    main()

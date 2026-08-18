"""Does repacking TWO bays together find moves repacking one cannot?

That is the only question worth asking first, and it is not the cost question.  The cost question
is already answered: a second bay is exactly 2x the columns and 2x the edges (measured,
harness/cpequiv.py bay2 -- 53,252 -> 106,504 and 95,965,518 -> 191,931,036), because cross-bay
pairs cannot conflict and are never enumerated.  And at the operator's REAL size the whole thing
is small anyway: 572 to 2,010 columns on the instances measured, not the 43,320 the top rung of
the tier ladder would generate.

What is NOT known is whether the larger neighbourhood pays.  The one-bay operator returned
nothing on P13, P25 and P20 even given 45 s, so "it is affordable" would be a useless finding on
its own.  The claim the two-bay form makes is specific: a trade that needs both bays to move at
once -- b leaves A for B while c leaves B for A, each fitting only in the hole the other opens --
is outside the one-bay neighbourhood entirely, not merely hard for it.  If that trade is real,
this arm finds gains where the other finds none.  If it is not, this arm finds the same nothing
at twice the price and the idea is dead, which is worth knowing in one run rather than five.

PAIRED, from one incumbent.  Both arms repack the SAME finished solution, so the difference is
the neighbourhood and not the solve that produced it -- and repack() is applied repeatedly from
its own output, because a single application is not how the operator runs and the compounding is
where the one-bay version's gain came from on P3.

    usage:  python3.12 harness/mbay.py <prob_id> [solve_s] [repack_s] [reps]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalgorithm as M          # noqa: E402
import bayrepack                 # noqa: E402
import utils                     # noqa: E402


def _reset():
    """Put bayrepack's learned state back where it starts, so arm 2 is not handed arm 1's
    calibration.  The geometry cache is left alone -- it is a pure function of the block."""
    bayrepack._CALLS[0] = 0
    bayrepack._RATIO[0] = 1.0
    bayrepack._PAIRRATE[0] = 6.4e-8
    bayrepack._CALIB[0] = False
    bayrepack._CALIB[1] = None


def _arm(d, sol, base, nbay, repack_s, reps):
    _reset()
    cur, obj = sol, base
    t0 = time.time()
    got = 0
    for _ in range(reps):
        left = repack_s - (time.time() - t0)
        if left <= 2.0:
            break
        out = bayrepack.repack(d, cur, left, M._total, M._build_operations,
                               engine_fn=getattr(M, "_ogc_fast_engine", None),
                               hard=left, nbay=nbay)
        if out is None:
            break
        chk = utils.check_feasibility(d, out)
        if not chk["feasible"]:
            print("    nbay=%d produced an INFEASIBLE solution -- stopping" % nbay, flush=True)
            break
        cur, obj, got = out, chk["objective"], got + 1
    return obj, got, time.time() - t0


def main():
    pid = sys.argv[1]
    solve_s = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    repack_s = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    reps = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    d = json.load(open("data/stage2/prob_%s.json" % pid))

    sol = M.algorithm(d, solve_s)
    base = utils.check_feasibility(d, sol)["objective"]
    print("P%-3s solved %.0fs  obj=%.0f  (bays=%d blocks=%d)"
          % (pid, solve_s, base, len(d["bays"]), len(d["blocks"])), flush=True)

    for nb in (1, 2):
        obj, got, el = _arm(d, sol, base, nb, repack_s, reps)
        print("P%-3s nbay=%d  %d application(s) in %.0fs  obj=%.0f  %+.2f%%"
              % (pid, nb, got, el, obj, 100.0 * (obj - base) / max(1.0, base)), flush=True)


if __name__ == "__main__":
    main()

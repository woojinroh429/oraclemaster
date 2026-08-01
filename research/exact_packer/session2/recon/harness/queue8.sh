#!/bin/bash
# THROUGHPUT.  Stop re-proving the feasibility of solutions that cannot become the answer.
#
# _total is the only selection criterion in the file, so it runs once per operator invocation
# plus once per bandit report.  It calls check_feasibility, which does two jobs at once: it
# re-derives w1*Z1 + w2*Z2 + w3*Z3 -- arithmetic over (bay, entry, exit) and nothing else --
# and it re-validates every crane path, which is polygon work.  Measured on the real hidden P3:
#
#     check_feasibility      173 ms
#     the arithmetic alone   0.13 ms          -- a factor of 1300
#
# and the arithmetic reproduces the grader's objective to the last digit, verified at two
# budgets.  So tens of seconds of every 240 s run go into re-proving the feasibility of
# solutions the engine has just built under that same rule.
#
# This matters twice over.  Every random draw in the worker loop is seeded, so what actually
# differs between two runs of one arm is how many operator calls fit in the budget -- which is
# why conw=0.0 returns 87,560 three times and 106,940 once.  Verification is a large and noisy
# share of that time, so removing it should narrow the spread as well as raise the ceiling, and
# the finals may give less time than the heats.
#
# Nothing that can be returned goes unverified.  A solution is screened on the arithmetic
# objective and checked for real before it is allowed to beat the incumbent; one that loses
# enters the pool on its cheap score, where the worst it can do is be bred from -- and breeding
# passes only the bay assignment to a beam that re-derives every placement itself.  It cannot
# climb to pool[0] later, because the pool grows and is truncated at the tail.  The closing
# best-of across workers and the final z3 pass stay fully verified.  run1.py now prints feas=
# so this is checked out loud on every line rather than inferred from the objective.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

OGC_DK=0 OGC_FASTOBJ=1 python3.12 harness/mkbase.py 0.3 myalg_fo.py     0 "" 0 1.0 "" 0 ""    >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1 python3.12 harness/mkbase.py 0.3 myalg_foc0.py   0 "" 0 1.0 "" 0 0.0   >/dev/null || exit 1
OGC_DK=0                python3.12 harness/mkbase.py 0.3 myalg_c0ctl.py 0 "" 0 1.0 "" 0 0.0   >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_fo as A, myalg_foc0 as B, myalg_c0ctl as C
for nm, M in (('fo', A), ('foc0', B)):
    s = inspect.getsource(M)
    assert 'def _fast_obj' in s and 'def _total(prob_info, sol, screen=None)' in s, nm
    assert 'pool[0][0] if pool else None' in s and 'band.tell(ai, _fast_obj' in s, nm
    assert s.count('o, _ = _total(prob_info, s)') == 1, (nm, 'closing best-of must stay real')
assert 'def _fast_obj' not in inspect.getsource(C), 'control must NOT carry the patch'
assert all(a.get('conw') == 0.0 for a in B._AXES) and all(a.get('conw') == 0.0 for a in C._AXES)
assert all(a.get('conw', 1.0) == 1.0 for a in A._AXES)
print('fastobj arms verified: fo (conw default) / foc0 (conw 0) / c0ctl (control, no patch)')" || exit 1

# A. does the screen change the answer at all, and is it still feasible?  Base conw, against a
#    band this arm has produced twenty times: 96,990 at the good end, 106,700 at the bad.
for rep in 1 2 3; do run myalg_fo "fastobj base r$rep" "q8_fo_r${rep}.log"; done

# B/C. the same question where the session's best result lives, paired.  conw=0.0 gave 87,560
#    on three runs of four and 106,940 on the fourth; if verification time was a real share of
#    the spread, B should hold 87,560 more often than C does, and may go under it.
for rep in 1 2 3 4; do
    run myalg_foc0  "fastobj conw0 r$rep" "q8_foc0_r${rep}.log"
    run myalg_c0ctl "control conw0 r$rep" "q8_c0ctl_r${rep}.log"
done
echo "queue8done  $(date -u +%H:%M:%S)"

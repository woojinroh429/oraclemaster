#!/bin/bash
# The tier rule, measured against the rule it replaced, INSIDE ONE QUEUE.
#
# WHAT brkcost FOUND.  On the real hidden P3, both of the packer's columns are step functions:
#
#     slice   took   ratio      obj     gain
#        8s   20.3s   2.5x   105,430   -1.19%
#       12s   18.9s   1.6x   105,430   -1.19%
#       20s   21.0s   1.1x   105,430   -1.19%
#       35s   77.0s   2.2x    91,670  -14.09%
#       60s   78.5s   1.3x    91,670  -14.09%
#      100s   81.0s   0.8x    91,670  -14.09%
#
# Time is set by the PROBLEM, not the budget -- small-tier calls cost ~20s and large-tier calls
# ~78s whatever they were asked for, because cranepack runs its own search to completion.  And
# the gain is quantised the same way: -1.19% small, -14.09% large, nothing between or above.
#
# THE RULE THAT REPLACED.  Tier chosen from the slice, large one gated at 40s.  brk's opening
# slot is worker_budget * 0.20 = 39.8s at a 240s run -- just under -- and deflating by the
# observed overrun ratio pushed it further under.  So brk ran in the -1.19% tier all session.
#
# THE NEW RULE.  Take the largest tier whose MEASURED cost fits the run's remaining time, with
# that remaining time passed in: a 40s slice with 190s left and a 40s slice with 45s left want
# opposite tiers and the slice alone cannot tell them apart.
#
# WHY THIS QUEUE EXISTS AT ALL.  queue20 compared the new rule against itself -- both its arms
# carried the fix -- so it could not say whether the fix helped.  The only other reference was
# queue12's and queue16's numbers, and arm levels have drifted between queues twice tonight
# (brk 82,180-86,550 then 88,720-91,670; conw0 87,560 then 113,200-116,420), each surviving a
# code diff and a contention check.  A fix scored against an earlier queue is not scored.
# BRK_OLDTIER=1 restores the old rule so both run here, interleaved.
#
# Any run over 240s is disqualified whatever it scored.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A, bayrepack as B
s = inspect.getsource(A)
assert 'hard=budget - (time.time() - t0)' in s, 'run-level remaining time not passed'
src = inspect.getsource(B.repack)
assert 'BRK_OLDTIER' in src and '_cap = (float(hard) if hard is not None else SL) * 0.85' in src
assert B._TIERS[0] == (4, 40, 3) and B._TIERCOST[0] > 50, (B._TIERS, B._TIERCOST)
print('both tier rules reachable; costs seeded at', B._TIERCOST)" || exit 1

run () {  # tag outfile  env...
    [ -s "results/$2" ] && return
    echo "=== $2  ($1)  $(date -u +%H:%M:%S)"
    env "${@:3}" python3.12 harness/run1.py myalg_brk 3 240 "$1" > "results/$2" 2>&1
    tail -1 "results/$2"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$2" >/dev/null 2>&1 \
      && git commit -q -m "result: $1" >/dev/null 2>&1 )
}

for rep in 1 2 3; do
    run "tier NEW r$rep" "q21_new_r${rep}.log"
    run "tier OLD r$rep" "q21_old_r${rep}.log" BRK_OLDTIER=1
done
echo "queue21done  $(date -u +%H:%M:%S)"

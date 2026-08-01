#!/bin/bash
# The tier fix, measured.  brk was running in the -1.19% tier all session.
#
# harness/brkcost.py, on the real hidden P3:
#
#     slice   took   ratio      obj     gain
#        8s   20.3s   2.5x   105,430   -1.19%
#       12s   18.9s   1.6x   105,430   -1.19%
#       20s   21.0s   1.1x   105,430   -1.19%
#       35s   77.0s   2.2x    91,670  -14.09%
#       60s   78.5s   1.3x    91,670  -14.09%
#      100s   81.0s   0.8x    91,670  -14.09%
#
# Both columns are step functions.  Time is set by the PROBLEM, not the budget -- every
# small-tier call costs ~20 s and every large-tier call ~78 s whatever it was asked for, because
# cranepack runs its own search to completion and treats the deadline as advisory.  And the gain
# is quantised the same way: -1.19% small, -14.09% large, nothing between, nothing above.  The
# large tier is four times the cost for twelve times the return.
#
# THE BUG THAT FOUND.  The old rule picked a tier from the slice with the large one gated at
# 40 s, and brk's opening slot is worker_budget * 0.20 = 39.8 s at a 240 s run.  Just under, and
# deflating by the observed overrun ratio pushed it further under.  So brk spent the entire
# session in the -1.19% tier while -14.09% sat one threshold away -- which is also why handing
# it the whole budget changed nothing: a bigger slice still bought the same small problem.
#
# THE FIX.  Take the largest tier whose MEASURED cost fits the run's remaining time, and pass
# that remaining time in, because the slice cannot distinguish 40 s with 190 s left from 40 s
# with 45 s left and those want opposite tiers.  Costs are learned per tier from what actually
# happens, seeded with the numbers above.
#
# Paired against brk-default IN THIS QUEUE, interleaved -- the brk-default runs so far split
# cleanly across queues, so cross-queue comparison is not available.  Any run over 240 s is
# disqualified whatever it scored.
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
assert B._TIERS[0] == (4, 40, 3) and B._TIERCOST[0] > 50, (B._TIERS, B._TIERCOST)
src = inspect.getsource(B.repack)
assert '_cap = (float(hard) if hard is not None else SL) * 0.85' in src
print('tier-by-measured-cost verified, seeded at', B._TIERCOST)" || exit 1

run () {  # tag outfile  env...
    [ -s "results/$2" ] && return
    echo "=== $2  ($1)  $(date -u +%H:%M:%S)"
    env "${@:3}" python3.12 harness/run1.py myalg_brk 3 240 "$1" > "results/$2" 2>&1
    tail -1 "results/$2"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$2" >/dev/null 2>&1 \
      && git commit -q -m "result: $1" >/dev/null 2>&1 )
}

for rep in 1 2 3; do
    run "tierfix full r$rep" "q20_full_r${rep}.log"
    run "tierfix solo r$rep" "q20_solo_r${rep}.log" OGC_OPS=beam,brk
done
echo "queue20done  $(date -u +%H:%M:%S)"

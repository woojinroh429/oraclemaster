#!/bin/bash
# Does beam+brk really have almost no spread, or is that two lucky samples?
#
# THE OBSERVATION.  Two runs of OGC_OPS=beam,brk returned 87,890 and 87,800 -- ninety points
# apart -- against the full roster's 82,180-91,670 over six runs, a spread of 9,490.  A factor
# of a hundred.  Both means are the same (87,845 against 87,703), so if it holds, dropping the
# other operators costs nothing in expectation and removes almost all the variance.
#
# WHY IT COULD BE REAL.  Every random draw in the worker loop is seeded, so what differs between
# two runs of one arm is how many slices each operator gets and in what order -- and that is
# decided by wall-clock timing through gain[i]/spent[i].  With six operators that is a long
# chain of timing-dependent branches; with two it is nearly deterministic.
#
# WHY IT MIGHT NOT BE.  Two samples.  This session has already called a 3-point trend monotone,
# a 3-run band halved, and a one-armed comparison a variance increase -- and retracted all three.
# A hundredfold claim on n=2 is exactly that mistake again, so it gets four more reps of each
# before anything is said about it.
#
# WHAT IT WOULD MEAN.  The finals may give less time than the heats, and a narrow band matters
# there more than a good best-case: a 240 s budget that sometimes returns 91,670 and sometimes
# 82,180 is worse to ship than one that always returns 87,850.  If this holds it is the first
# real answer to that, and it is free -- the operators it drops are the ones p3max proved
# structurally dead on this instance anyway.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1

run () {  # tag outfile  env...
    [ -s "results/$2" ] && return
    echo "=== $2  ($1)  $(date -u +%H:%M:%S)"
    env "${@:3}" python3.12 harness/run1.py myalg_brk 3 240 "$1" > "results/$2" 2>&1
    tail -1 "results/$2"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$2" >/dev/null 2>&1 \
      && git commit -q -m "result: $1" >/dev/null 2>&1 )
}

# Interleaved so any drift over the queue's life hits both arms equally.
for rep in 3 4 5 6; do
    run "brk solo r$rep" "q19_solo_r${rep}.log" OGC_OPS=beam,brk
    run "brk full r$rep" "q19_full_r${rep}.log"
done
echo "queue19done  $(date -u +%H:%M:%S)"

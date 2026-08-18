#!/bin/bash
# THE ASK IS THE SLICE AGAIN -- but nothing predicts the build any more.
#
# A brk call is BUILD (an O(ncol^2) graph construction that cannot be interrupted) plus SEARCH
# (a set-packing local search that honours a deadline).  The deadline handed to the search is
# the ask, and it is the only part of the call that can be bounded directly.
#
# There are two different questions and only one was being asked:
#
#     hard * 0.85   does this CALL fit inside the run's deadline
#     slice         does this OPERATOR leave room for the others
#
# Dropping the slice this morning was right for the reason given then -- the slice capped the
# TIER CHOOSER too, and on P3 that switched off the lever worth 16,000.  What I did not keep was
# its other job.  While the build was slow it did not matter: a 96 s cap minus a 60 s build left
# 36 s of search.  With the build 10x faster the same cap hands the search 100 s, and P4 spent
# 267-287 s of a 480 s budget in a single call and finished at 491 s, which is not scored.
#
# So: cranepack now takes BOTH bounds and uses whichever is tighter against its own MEASURED
# build.  The slice bounds the search; hard bounds the call; neither predicts anything.  The
# tier chooser still sees the run-level room, so the P3 lever stays reachable.
#
# BASELINES ON THIS HOST, all feas=y:
#     P3       80,795  @ 239/240      P4  1,981,906 @ 491/480   OVER
#     P6   29,583,182  @ 900/900      P5  9,526,639 @ 599/600
# and from the faster host, for direction only: P4 1,781,181, P5 9,044,458.
#
# P4 FIRST: it is the one that failed the budget, and a fix that does not bring it under 480 s
# is not a fix.  Then P5, then P3 to confirm the slice does not cost back the 80,795.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

python3.12 -c "
import inspect, bayrepack as R
c = open('cranepack.cpp').read()
assert 'std::min(time_budget_s' in c, 'cranepack ignores one of the two bounds'
r = inspect.getsource(R)
assert '_ask = max(_MINASK, SL)' in r, 'the ask is not the slice'
assert '_cap - _PAIRRATE' not in r, 'the double charge is back'
print('verified: search bounded by the slice, call bounded by hard, nothing predicted')" || exit 1

run () {  # prob secs tag outfile
    [ -s "results/$4" ] && return
    echo "=== $4 ($3) $(date -u +%H:%M:%S)"
    BRK_DEBUG=1 timeout $(( $2 * 5 + 300 )) \
        python3.12 harness/run1.py myalgorithm "$1" "$2" "$3" > "results/$4" 2>&1
    tail -1 "results/$4"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$4" >/dev/null 2>&1 \
      && git commit -q -m "askcap: $3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run 4 480 "askcap P4" "ac_p4.log"
run 5 600 "askcap P5" "ac_p5.log"
run 3 240 "askcap P3" "ac_p3.log"
run 6 900 "askcap P6" "ac_p6.log"
echo "askcap done $(date -u +%H:%M:%S)"

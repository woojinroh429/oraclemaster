#!/bin/bash
# THE ONLY COMPARISON THAT DECIDES WHAT TO SHIP: both builds, all six problems, real budgets.
#
# The submission is scored by the server on P1 through P6.  I spent today comparing builds on P3
# and P4 alone and was about to pick one on that basis, which is two instances out of six.
# P1, P2, P5 and P6 have not been measured for either build.
#
# Budgets from HIDDEN_SET.md (the preliminary final report):
#
#     P1   60 s   3 bays  100 blocks   w1 21,622  w2 10  w3 150
#     P2  120 s   2 bays  150 blocks   w1  8,000  w2  4  w3 200
#     P3  240 s   3 bays  200 blocks   w1 17,778  w2  5  w3 150
#     P4  480 s   3 bays  150 blocks   w1 13,333  w2  7  w3 150
#     P5  600 s   4 bays  200 blocks   w1 13,333  w2  7  w3 133
#     P6  900 s   3 bays  250 blocks   w1  6,667  w2  8  w3 150
#
# THE TWO BUILDS.
#
#   myalgorithm.py   what ships today.  P3 90,545 (twice, to the digit); P4 3,273,791.
#   myalg_a          mkbase's arm, DK=0 FASTOBJ=1, brk OFF.  P3 ~96,990-106,700; P4 1,780,253.
#
# brk is excluded deliberately.  On P4 it either loses to its own control (1,981,906 against
# 1,780,253) or, once its budget rule stopped over-committing, lands exactly on it (1,781,181).
# The 39% was never brk's, and brk's P3 gain does not survive any principled budget rule --
# queue29 gave 86,665 and 92,760 from the SAME configuration.
#
# The rulers have been checked: c80551b scores 30,297,335 here against the real grader's
# 29,396,046 on P6, 3.1% apart on a single 900 s stochastic run, so these numbers are
# comparable to the leaderboard's.
#
# Interleaved per problem, cheapest first, so a container restart (two today) costs one pair
# rather than a whole build, and each result is pushed as it lands.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 python3.12 harness/mkbase.py 0.3 myalg_a.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalgorithm as S, myalg_a as A
s, a = inspect.getsource(S), inspect.getsource(A)
assert 'bayrepack' not in s and 'bayrepack' not in a, 'neither build may carry brk'
assert 'dk=0' in a and 'def _fast_obj' in a, 'the arm is not DK=0 FASTOBJ=1'
assert s != a, 'the two builds are the same file'
print('both builds verified: shipped vs mkbase arm, neither carrying brk')" || exit 1

run () {  # module prob secs tag outfile
    [ -s "results/$5" ] && return
    echo "=== $5  ($4)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" "$2" "$3" "$4" > "results/$5" 2>&1
    tail -1 "results/$5"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$5" >/dev/null 2>&1 \
      && git commit -q -m "sixway: $4" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

for pb in "1 60" "2 120" "3 240" "4 480" "5 600" "6 900"; do
    set -- $pb
    run myalgorithm "$1" "$2" "SHIP P$1" "six_ship_p$1.log"
    run myalg_a     "$1" "$2" "ARM  P$1" "six_arm_p$1.log"
done
echo "sixway done  $(date -u +%H:%M:%S)"

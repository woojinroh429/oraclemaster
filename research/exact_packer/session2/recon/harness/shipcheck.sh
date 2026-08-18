#!/bin/bash
# Does the build we intend to ship stay inside its budget, and keep its numbers?
#
# The arm to ship is myalg_brk: P3 86,665 against the submission's 90,545, and P4 1,981,906
# against the submission's 3,273,791.  Both better.  One thing blocks it:
#
#     P4 brk on   1,981,906   ran 720 s against a 480 s budget
#
# At the grader's hard limit a 50% overrun is a MISSING answer, not a worse one, so that number
# would not have been scored at all.
#
# THE CAUSE, and it is structural.  cranepack builds its conflict graph with a plain O(ncol^2)
# double loop that never looks at the clock -- the search loop honours time_budget_s, the build
# cannot even see it.  An oversized pack therefore cannot be cut short; it can only be declined
# before it starts.  The tier table was seconds measured on P3's 43x23 bay, and the same tier
# generates a flood of columns in a larger one, so the table could not decline anything.
#
# THE FIX.  Predict from seconds-per-squared-column, measured on the machine actually running:
# estimate the columns a tier would generate from the target bay's size and its candidate list,
# take the largest tier the remaining run can absorb, and if even the smallest does not fit,
# do not call the packer at all.  The first call in a process is uncalibrated, so it takes the
# smallest tier -- cheap everywhere, and it is what calibrates the rate.
#
# P4 FIRST, because staying inside 480 s is the thing that has to hold; the objective is the
# second question.  Then P3, to check the fix has not cost the -4.3% that motivates shipping it.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A, bayrepack as R
a, r = inspect.getsource(A), inspect.getsource(R)
assert 'import bayrepack as _brk' in a and 'hard=budget - (time.time() - t0)' in a
assert '_PAIRRATE' in r and '_TIERCOST' not in r, 'size-predicted tier selection not wired'
assert 'declined, smallest tier predicts' in r, 'the decline path is missing'
print('arm and size-predicted packer budget verified')" || exit 1

run () {  # prob secs tag outfile
    [ -s "results/$4" ] && return
    echo "=== $4  ($3)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py myalg_brk "$1" "$2" "$3" > "results/$4" 2>&1
    tail -1 "results/$4"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$4" >/dev/null 2>&1 \
      && git commit -q -m "shipcheck: $3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run 3 240 "FIT P3 r1" "fit_p3_r1.log"
run 4 480 "FIT P4 r1" "fit_p4_r1.log"
run 3 240 "FIT P3 r2" "fit_p3_r2.log"
echo "shipcheck done  $(date -u +%H:%M:%S)"

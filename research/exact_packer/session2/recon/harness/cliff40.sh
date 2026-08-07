#!/bin/bash
# STEP 1 OF THE VARIANCE PROGRAM: FIND THE REMAINING CLIFFS.
#
# results/audit/variance_source.md establishes that every RNG in the algorithm is constant-seeded,
# so the ONLY input that differs between two runs of the same build on the same instance is
# time.time() -- and those runs come back 16.2% apart (P16 base: 3,813,686 vs 3,281,165).  All of
# the run-to-run spread is therefore timing, and timing noise is the same thing as noise in the
# EFFECTIVE budget.
#
# That makes obj(T) the diagnostic.  Where the curve is smooth, a slow machine costs a little
# quality.  Where it jumps, a slow machine loses the instance outright -- and every jump is a
# discrete decision that throws away completed work.  The only change that ever clearly won on
# this project, beam salvage, was exactly one such jump: prob_36 returned 4,023,023,433 at 110 s
# against 96,871,459 at 130 s, a factor of 42, because a partial beam was discarded rather than
# finished.  That ladder has NOT been re-run since salvage landed, so which cliffs remain is
# simply unknown.
#
# WHY ONE DRAW PER POINT IS ENOUGH.  It is not enough to measure a slope -- the noise is 2.5-16%.
# It is plenty to find a cliff: the ones already found were 42x, 143x and 250x.  This is a hunt
# for order-of-magnitude jumps, and spending the budget on more budget-points beats spending it
# on replicates of a point.
#
# WHY THESE SIX BUDGETS.  The hidden per-instance limits are not disclosed and the rules say they
# vary across problems.  Everything in results/stage2 was run at 60, the technical report's own
# comparisons used 180, and 240 is the figure to plan around.  60-300 spans the plausible range;
# below 60 every large instance cliffs and the answer would say nothing about a real run.
#
# INSTANCE-MAJOR, biggest first.  A finished instance is a complete curve that can be read at
# once, and the cliffs found so far were all on 250-300 block instances, so the informative half
# of the sweep lands first.  ~16.5 min of budget per instance, about 13 h for all forty.
#
# OGC_WSTAT records what each of the four workers returned, because a cliff where all four are
# bad and one where three are fine and the minimum rescues us are different defects.
set -u
cd "$(dirname "$0")/.." || exit 1
echo cliff40 > harness/CURRENT
L=results/audit/cliff40.log
mkdir -p results/audit; touch $L

BUDGETS="60 90 120 180 240 300"
# by block count, descending: 300s first, then 250, 200, 150
ORDER="40 36 34 30 26 25 23 16 13 12 35 28 20 17 15 14 11 6 4 2 38 32 31 29 27 19 18 9 8 3 39 37 33 24 22 21 10 7 5 1"

run(){ # prob budget
    local tag="c.$1.$2"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_WSTAT=1 timeout $(( $2 * 3 + 240 )) /usr/bin/python3.12 harness/run1.py myalgorithm $1 $2 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$1 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/cliff40.log \
      && git commit -q -m "in-flight: cliff40 $tag" ) >/dev/null 2>&1
}

for p in $ORDER; do
    for T in $BUDGETS; do
        run $p $T
    done
    echo "CURVEDONE $p" >> $L
done
echo "CLIFF40DONE" >> $L
echo idle > harness/CURRENT

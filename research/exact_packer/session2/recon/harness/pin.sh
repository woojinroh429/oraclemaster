#!/bin/bash
# WHERE THE RUN-TO-RUN VARIANCE COMES FROM, AND WHETHER ONE SWITCH REMOVES IT.
#
# Every RNG in myalgorithm.py is constant-seeded -- Random(1234+wid), Random(20260731),
# Random(90001+7919*wid) -- and wid, the aim split and the axis rotation are fixed.  So two runs of
# one build on one instance at one budget differ in exactly ONE input: time.time().  They come back
# 2.5% to 25% apart.
#
# The amplifier is in ogc_fast.cpp, recomputed at EVERY level (300 of them on a 300-block instance):
#
#     per  = elapsed()/work;                   <- wall clock
#     left = time_budget_s*AIM - elapsed();    <- wall clock
#     Bcur = min(Bmax, left/(per*rem));        <- this level's beam width
#
# Scheduling jitter moves `per`, which moves the width, which changes how many states survive a
# DISCRETE top-B cut, which changes the cost of the next level, which moves `per` again.  Three
# hundred rounds of a control loop driven by measurement noise and feeding back into it.  Two runs
# differing by one surviving state at level 5 share nothing by level 50.
#
# OGC_ADAPTB=0 pins the width for the whole run and that loop is gone.  ADAPTK rides on the same
# flag, so the per-state candidate count stops moving with the clock too.
#
# The second amplifier is in the Python operator loop: selection is gain[i]/spent[i] with spent in
# SECONDS, and a repair pass is resized to 1.3x whatever it just took.  OGC_DET charges each
# operator the slice it was GIVEN and shrinks repair passes by a fixed factor, so selection depends
# only on exact integer gains and on arithmetic over the budget.  The `det` arm runs both, because
# removing one amplifier while the other still feeds on jitter answers very little.
#
# What is deliberately NOT removed: the stops.  `left = budget - elapsed`, the beam's deadline, the
# reserve.  The budget is real time and those have to read the clock.  The claim under test is only
# that DECISIONS need not.
#
# WHY THIS IS SAFER NOW THAN WHEN THE CONTROLLER WAS ADDED.  _beam_width's own docstring says a
# fixed width "was silently catastrophic -- the beam returns NOTHING when it overruns ... so every
# worker fell back to the greedy floor and the 300s answer came out worse than the 60s one."  Beam
# salvage removed that failure mode: an overrun now completes the partial by rollout instead of
# returning nothing.  The reason the adaptive controller exists has been fixed since.
#
# MEASURED ACROSS RUNS, NOT ACROSS WORKERS.  Worker spread is (max-min)/min and the answer is min,
# so it is correlated with quality by construction -- that mistake cost this session eight false
# confirmations.  This repeats the SAME configuration five times and reports the spread of the five
# FINAL objectives, which has no such coupling and is the variance that actually reaches the score.
set -u
cd "$(dirname "$0")/.." || exit 1
echo pin > harness/CURRENT
L=results/audit/pin.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 1200 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/pin.log \
      && git commit -q -m "in-flight: pin $tag" ) >/dev/null 2>&1
}

# rep-major: five repeats of each arm on each instance, so a partial queue is still balanced
for rep in 1 2 3 4 5; do
    for p in 24 20 6; do
        run $rep adapt  $p "OGC_POLISH=1"
        run $rep pinned $p "OGC_POLISH=1 OGC_ADAPTB=0"
        run $rep det    $p "OGC_POLISH=1 OGC_ADAPTB=0 OGC_DET=1"
    done
    echo "REPDONE $rep" >> $L
done
echo "PINDONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# DOES THE MONOTONE WIDTH LADDER REMOVE THE BAD TAIL?
#
# The measured fact this queue tests against: the same build, same instance, same budget, minutes
# apart, returns 2,795,643 and 3,612,529 on prob_16 -- and returns prob_24 to the digit.  Two
# determinism arms were built (OGC_ADAPTB=0, OGC_DET) and neither shrank the spread; pinning the
# width made prob_16 WORSE, 10.4% -> 27.9%.  So the variance is the instance's landscape, not
# clock jitter, and the thing to buy is not determinism but MONOTONICITY.
#
# Why a bigger budget can lose: Bcur = min(Bmax, left/(per*rem)) is derived from the budget, so
# 240 s does not run the 60 s search for longer -- it runs a WIDER search, once.  Nothing carries
# the narrow answer forward.  prob_16 reaches 2.79M at 60 s and reached it once in ten 240 s draws.
#
# OGC_MONO=1 runs a narrow beam first (OGC_MONOW of the width, OGC_MONOF of the slice), KEEPS its
# solution, then runs the normal ladder on the rest and returns whichever scores better.  Same
# shape as beam salvage -- the one change on this project that clearly worked, which was "finish
# the partial instead of discarding it".  This is "compare instead of discarding".
#
#     ship    as shipped (polish ON)          <- what any change has to beat
#     m1      polish off                      <- isolates the polish removal from the ladder
#     mono    polish off + ladder 0.25/0.25   <- one cheap narrow rung
#     monoB   polish off + ladder 0.35/0.35   <- a rung wide enough to be competitive on its own
#
# prob_24 is in the set as a CONTROL: it repeats to the digit today, so if the ladder costs
# anything by construction it shows up there as a regression with no variance to blame.
#
# Read with:  python3 harness/beamside.py results/audit/mono.log   (min AND median worker --
# the polish inflated every earlier arm comparison, 419 of 804 runs gaining exactly nothing).
set -u
cd "$(dirname "$0")/.." || exit 1
echo mono > harness/CURRENT
L=results/audit/mono.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 1200 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/mono.log \
      && git commit -q -m "in-flight: mono $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
    for p in 16 4 20 24; do
        run $rep ship  $p "OGC_POLISH=1"
        run $rep m1    $p ""
        run $rep mono  $p "OGC_MONO=1"
        run $rep monoB $p "OGC_MONO=1 OGC_MONOW=0.35 OGC_MONOF=0.35"
    done
    echo "REPDONE $rep" >> $L
done
echo "MONODONE" >> $L
# chain straight into the beam-strengthening queue, which was killed at 6 of 60 cells
echo beamhard > harness/CURRENT
nohup bash harness/beamhard.sh >> results/beamhard.log 2>&1 < /dev/null &

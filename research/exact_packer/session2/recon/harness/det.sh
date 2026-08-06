#!/bin/bash
# STEP 3+2: DOES REMOVING THE CLOCK NARROW THE SPREAD, AND DOES A LOSING WORKER'S REMAINING
# BUDGET BUY A DRAW?  (The CONVERGED-worker form was built, smoke-tested and dropped: it fired
# once in a 120 s run because every worker keeps improving its own answer to the end.  The arm
# here is the RELATIVE one -- redraw a worker that is behind the field, which every WSTAT row
# cliff40 produced shows is 15-30% of the portfolio, every run.)  Three arms, because the two changes are independent and the second is the
# one with a number attached to it (4 draws -> 12 is worth ~4.7% and -19% on the SD of the answer,
# from the simulated statistics of a minimum at the measured sigma ~ 7.8%).
#
# Established, not assumed: every RNG in myalgorithm.py is constant-seeded, and wid, the aim split
# and the axis rotation are fixed -- so two runs of one build on one instance at one budget differ
# in exactly one input, time.time().  Measured consequences: stage-2 P16 returned 3,813,686 and
# 3,281,165 on two runs of the identical build (16.2%), and the fourth submission -- byte-identical
# to the third but for one docstring word -- moved a hidden instance by 8.66% and the total by
# 1.33%.  That is the entire reason submissions jump.
#
# myalg_det.py is myalgorithm.py plus one env knob.  With OGC_DET unset it is the same code path.
# With OGC_DET=1 the operator loop charges each operator the slice it was GIVEN instead of the
# seconds it burned, and a repair pass that completed shrinks by a fixed factor instead of to a
# multiple of its own runtime.  Selection then depends only on exact objective gains and on
# arithmetic over the budget.
#
# WHAT IS BEING MEASURED IS THE SPREAD ACROSS REPLICATES OF THE SAME ARM, which is why three
# replicates per cell and only six instances: comparing the two arms' medians answers "did it cost
# quality", but the question that matters is whether arm det's three draws sit closer together
# than arm base's three.  A change that leaves the median alone and halves the spread is the win.
#
# It will NOT make runs identical and this queue is not a test of that.  The operators are still
# handed seconds and the C++ beam still races a wall-clock deadline, so a faster machine still
# searches deeper.  One of three couplings is removed here; the beam's is the expensive one and
# comes after, if this shows the mechanism is worth the work.
set -u
cd "$(dirname "$0")/.." || exit 1
echo det > harness/CURRENT
L=results/audit/det.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -q "\[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py $5 $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/det.log \
      && git commit -q -m "in-flight: det $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 16 6 20 1 36 34; do
        run $rep base $p ""              myalgorithm
        run $rep det  $p "OGC_DET=1"     myalg_det
        run $rep rdrw $p "OGC_RESTART=2" myalg_det
    done
    echo "REPDONE $rep" >> $L
done
echo "DETDONE" >> $L
echo idle > harness/CURRENT

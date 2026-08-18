#!/bin/bash
# BUY WORK BY MAKING THE UNIT CHEAPER, WHICH IS THE ONLY MULTIPLE LEFT.
#
# WHY THE OTHER ACCELERATIONS WERE NOT ENOUGH.  accel proved both dark engine knobs bit-identical
# under a fixed work cap and then measured them: OGC_DEDUP=0 is 2.1% faster, OGC_FCACHE=1 is twice
# as SLOW.  2% does not matter when three times the clock is worth -30.7% on prob_1.
#
# WHERE THE WIDTH ACTUALLY COMES FROM.  ogc_fast.cpp:1957 sets the beam width per level as
#
#     Bcur = left / (per * rem)        per = elapsed/work, rem = levels remaining
#
# so width is inversely proportional to the cost of ONE state expansion.  BEAMSTAT confirms the
# consequence: prob_1 reports work=353 over 150 levels with Bmax=96 and capped=0 -- an average
# width near 2.4, never within sight of the ceiling.  The beam is not width-limited, it is
# cost-limited, and no amount of raising OGC_BCAP can touch that.
#
# THE UNIT IS THE POSITION SCAN, AND IT HAS A STRIDE.  `step` is the grid stride in
# best_cell_contact_tl; step 2 examines half the positions on each axis, a quarter of the cells,
# for roughly a quarter of the cost -- which by the formula above is about four times the width,
# hence four times the work at the same depth and budget.
#
# AND prob_1 IS KNOWN TO WANT WORK.  myalgorithm.py's own reserve note: "the deterministic table
# says prob_1's best axis is still improving at work 12,000 (51 s) while production stops it
# around 9 s".  flatctl measured the same limit from the other side -- 3x the wall clock, -30.7%.
#
# NOTHING HAS EVER ASKED, because the rung loop hard-coded ((1, FINEFRAC), (2, 1.0)) and returns on
# the first feasible answer, so step 2 runs only when step 1 fails outright.  In the normal case
# the coarse rung never executes and the 40% of the slice reserved for it is simply not spent --
# the same shape of defect the fill gate turned out to be.  OGC_STEPS makes the rung list a knob;
# its default "1,2" reproduces the old tuple byte for byte (verified against the literal).
#
# ARMS:
#     A  STEPS 1,2   FINEFRAC 0.60    shipped, the control
#     B  STEPS 1,2   FINEFRAC 0.85    fine rung gets more of the slice (task #13, never measured)
#     C  STEPS 1,2   FINEFRAC 1.00    fine rung gets all of it; coarse rung only on failure
#     D  STEPS 2                      coarse rung ALONE -- the 4x-work arm
#     E  STEPS 2,1                    coarse first, fine with what is left
#
# WHAT WOULD MAKE IT FAIL, named first, and D is the one with a real mechanism against it.  A
# coarser grid cannot express every placement a fine one can, so every individual answer is worse;
# the bet is only that four times as many states beats four times the resolution.  If prob_1 is
# limited by the QUALITY of placements rather than their count, D loses outright and the work
# argument was the wrong reading of that deterministic table.
#
# C's named risk is recorded in the code it changes: with the fine rung handed the whole slice,
# "two of three beam calls returned nothing at all" on prob_18 at n=300 in a 12 s slice.  That is
# why the reserve exists.  prob_16 (n=300) is carried here for exactly that failure, and a cell
# that returns the _safe_sequential floor kills the arm regardless of its other numbers.
#
# JUDGED, fixed before the run: floor first (any arm producing a >1e9 objective is out), then
# paired ratio against A within replicate, median over three, prob_1 deciding and prob_3/prob_16
# vetoing.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire gridstep
L=results/audit/gridstep.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/gridstep.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/gridstep.sh \
        && git commit -q -m "in-flight: gridstep $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" env0="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_BEAMSTAT=1 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3 16; do
    run "A.p$p.r$rep" $p ""
    run "B.p$p.r$rep" $p "OGC_FINEFRAC=0.85"
    run "C.p$p.r$rep" $p "OGC_FINEFRAC=1.0"
    run "D.p$p.r$rep" $p "OGC_STEPS=2"
    run "E.p$p.r$rep" $p "OGC_STEPS=2,1"
  done
done
echo "GRIDSTEPDONE" >> $L
lock_release gridstep

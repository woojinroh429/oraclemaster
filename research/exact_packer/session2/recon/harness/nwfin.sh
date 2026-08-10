#!/bin/bash
# FINISH P3, SKIP P4, THEN MEASURE THE PART OF THE SCORE NOBODY HAS LOOKED AT.
#
# All three budgets the shipped gate fires at return byte-identical answers under either worker
# count, on the instances that actually stand in for hidden problems:
#
#     P1   60 s  train/prob_2   100 blk 3 bays   6/6 identical   spent 60% of budget
#     P2  120 s  train/prob_8   150 blk 2 bays   6/6 identical   spent 64%
#     P3  240 s  train/prob_9   200 blk 3 bays   2/2 identical   spent 98%
#
# P3 matters because it is starved -- 236 s of 240 -- and starvation is the one condition under
# which extra cores per worker can buy anything.  It bought nothing.  So nw = cpu-1 for
# timelimit <= 240 is inert on every scored problem it touches, and P4/P5/P6 are byte-identical to
# the previous submission because the gate is off there.  The change is harmless and worthless.
#
# P4 IS CANCELLED.  Six runs at 480 s is 96 minutes to characterise a cell where the gate is OFF;
# no decision depends on the answer, because whatever w3 does at 480 s is not what will run.
#
# WHAT IS WORTH THE TIME INSTEAD.  From friend_ref/README.md:
#
#     P1     11,280      P2     31,368      P3      93,395
#     P4  2,460,584      P5 10,128,108      P6  32,366,596
#
# P5 and P6 are three orders of magnitude above P1-P3 and have never been run at 600 s or 900 s in
# this session.  And the first question there is NOT the worker count -- the gate cannot reach
# them -- it is whether the run-to-run spread this entire night was spent chasing exists there at
# all.  Every hidden analogue measured so far has a spread of exactly zero.  If P5 and P6 are the
# same, then the 11-33% spread that defeated thirteen arms tonight is a property of stage-2
# prob_1 and prob_16 and of nothing that is scored, and no variance-reduction arm could ever have
# paid.  If they DO vary, it is the first sighting of the reported problem at the budgets that
# carry the score.
#
# w4 ONLY at 600/900 s: the gate is off there, so w4 IS the shipped behaviour, and three draws of
# it measure the spread of what will actually run.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nwfin > harness/CURRENT
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nwreal.log \
                  research/exact_packer/session2/recon/results/audit/nwbig.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nwfin.sh \
        && git commit -q -m "in-flight: nwfin $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # log tag prob limit env
    local L="$1" tag="$2"
    mkdir -p results/audit; touch $L
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $5 OGC_WSTAT=1 timeout $(( $4 * 2 + 180 )) /usr/bin/python3.12 harness/run1.py myalgorithm $3 $4 \
        "[$tag]" --data data/train >> $L 2>&1 || echo "P$3 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

R=results/audit/nwreal.log
B=results/audit/nwbig.log

for rep in 2 3; do
  run $R "P3.r$rep.p9.w4" 9 240 "WORKERS=4"
  run $R "P3.r$rep.p9.w3" 9 240 "WORKERS=3"
done
echo "== NWFIN P3 done (P4 deliberately skipped) ==" >> $R

for rep in 1 2 3; do
  run $B "P5.r$rep.p10.w4" 10 600 "WORKERS=4"
done
echo "== NWFIN P5 (prob_10 600s) done ==" >> $B
for rep in 1 2 3; do
  run $B "P6.r$rep.p37.w4" 37 900 "WORKERS=4"
done
echo "NWFINDONE" >> $B
echo idle > harness/CURRENT

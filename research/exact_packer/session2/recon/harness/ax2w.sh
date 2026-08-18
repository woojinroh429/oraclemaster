#!/bin/bash
# THE DEPLOYABLE FORM: GIVE AXIS 2 THE WIDTH, KEEP THE PORTFOLIO.
#
# prob_16 at 240 s, separated:
#
#     stock                          3,010,278  3,179,204   mean 3,094,741   control span 5.6%
#     OGC_AXIS=2 alone                          2,932,602   -2.6%
#     OGC_BCAP=137 alone                        3,018,252   -2.5%
#     OGC_AXIS=2 with OGC_BCAP=137   2,725,778  2,913,538   mean 2,819,658   -8.9%
#
# The gain is the interaction: axis 2 carries Bmul=0.7 so production runs it at B=67, and its
# scoring only pays once it stops being starved.  Neither route to it is shippable, though --
# OGC_BCAP raises the ceiling for every axis, and OGC_AXIS pins the entire pool to one axis whose
# dominance axis_work.md measured as unique to prob_16 (prob_4's winner flips to axis 1 at the
# largest budget, prob_24 answers axis 0 or 5).
#
# OGC_BMULSET=1.0,1.0,1.0,0.7,1.4,0.5 raises axis 2's own Bmul from 0.7 to 1.0 and leaves the other
# five exactly as they are.  One worker in four stops being starved; the rotation still covers
# every other axis, so an instance whose best axis is not 2 is untouched.  No gate, no prediction.
#
# WHERE IT SHOULD LAND, written before the runs.  Between -2.5% (ceiling raised for everyone) and
# -8.9% (axis 2 given the whole pool), because axis 2 gets one worker rather than four.  Below -5%
# is worth shipping; at or above -2.5% it is doing nothing the ceiling was not already doing.
#
# AND prob_4 IS THE CONTROL THAT MATTERS.  It is the instance where axis 2 does NOT dominate, so it
# prices what widening a non-winning axis costs.  If prob_4 regresses, the change is instance-fitted
# and the table should not move.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo ax2w > harness/CURRENT
L=results/audit/ax2w.log
mkdir -p results/audit; touch $L
BM="OGC_BMULSET=1.0,1.0,1.0,0.7,1.4,0.5"
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ax2w.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/ax2w.sh \
        && git commit -q -m "in-flight: ax2w $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_WSTAT=1 timeout 560 /usr/bin/python3.12 harness/run1.py myalgorithm $2 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  run "b2.p16.r$rep" 16 "WORKERS=4 $BM"
done
echo "== AX2W prob_16 done ==" >> $L
for rep in 1 2 3; do
  run "b2.p4.r$rep"  4 "WORKERS=4 $BM"
  run "b2.p4c.r$rep" 4 "WORKERS=4"
done
echo "AX2WDONE" >> $L
echo idle > harness/CURRENT

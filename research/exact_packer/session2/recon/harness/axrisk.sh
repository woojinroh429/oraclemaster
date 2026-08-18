#!/bin/bash
# WHAT DOES PINNING AXIS 2 COST WHERE AXIS 2 IS NOT THE ANSWER?
#
# Only one arm on prob_16 has held up, and it is the one that cannot ship as it stands:
#
#     stock                       5 draws   mean 3,026,682
#     OGC_AXIS=2 + OGC_BCAP=137   3 draws   mean 2,738,943   -10.4%, no overlap with stock
#     OGC_BCAP=137 alone          4 draws   mean 2,981,033    -2.5%
#     OGC_BMULSET (axis 2 only)   5 pairs   mean       +1.4%   2 wins 3 losses -- dead
#
# Widening axis 2 on ONE worker does nothing.  The gain needs all four workers on axis 2 at B=96,
# which means giving up the portfolio -- and axis_work.md measured axis 2's dominance as unique to
# prob_16: margin 2.05x-2.51x there, under 1.2x on prob_4 and prob_24, with prob_4's winner
# flipping to axis 1 and prob_24's to axis 0 or 5 at the largest budget.
#
# So the whole direction now rests on one number nobody has measured: what pinning costs on an
# instance whose best axis is not 2.  prob_4 is that instance, at the same 3M objective scale.
#
#     small cost   ->  pin without a gate; the portfolio was insurance against a risk that is small
#     large cost   ->  a gate is required, which needs to know the dominant axis BEFORE round 0 --
#                      the same shape as the brk gate and the axis gate, both of which died this
#                      session for want of a predictor
#
# prob_4 FIRST because it decides.  prob_1 second as a third shape.  Five pairs each: prob_16's
# stock arm spans 9.5% and every three-draw reading tonight has been overturned by the fourth.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo axrisk > harness/CURRENT
L=results/audit/axrisk.log
mkdir -p results/audit; touch $L
PIN="OGC_AXIS=2 OGC_BCAP=137"
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/axrisk.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/axrisk.sh \
        && git commit -q -m "in-flight: axrisk $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_WSTAT=1 timeout 560 /usr/bin/python3.12 harness/run1.py myalgorithm $2 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4 5; do
  run "x.p4.stock.r$rep" 4 "WORKERS=4"
  run "x.p4.pin.r$rep"   4 "WORKERS=4 $PIN"
done
echo "== AXRISK prob_4 done ==" >> $L
for rep in 1 2 3 4 5; do
  run "x.p1.stock.r$rep" 1 "WORKERS=4"
  run "x.p1.pin.r$rep"   1 "WORKERS=4 $PIN"
done
echo "AXRISKDONE" >> $L
echo idle > harness/CURRENT

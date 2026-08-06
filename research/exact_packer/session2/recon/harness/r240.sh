#!/bin/bash
# More draws instead of deeper ones, at a budget large enough to afford the split.
#
# WHY THIS AND NOT ANOTHER AXIS ARRANGEMENT.  b240 settled that dispatch order is not what makes
# the answer move: four different orders returned the IDENTICAL objective on P1, a 4-axis set and
# the shipped 6-axis set returned byte-identical objectives on P6, and across 240 s runs the
# arm-to-arm differences were 2-5% while the SAME arm moved 2.5-16% between draws.  Re-running one
# configuration changes the answer more than changing the configuration does.
#
# So the thing to attack is the spread itself, and the algorithm already has the lever for it.
# OGC_ROUNDS runs R rounds of nw workers at budget/R each and keeps the minimum across all of
# them.  The distribution of a minimum tightens as draws are added -- that is the whole mechanism
# -- and it is off by default.
#
# It was measured once, at 60 s, and lost: median +0.91% at R=2.  The reason is visible in the
# numbers rather than assumed -- at 60 s each worker already has little, so halving it makes every
# draw too shallow to reach a good basin, and more shallow draws is a worse trade than fewer deep
# ones.  At 240 s a half is 120 s, which is twice what the 60 s runs had in total.  The combination
# of a large budget and R>1 has never been run.
#
# WHAT IS BEING MEASURED IS THE SPREAD, NOT THE MEAN.  A change that leaves the median alone and
# halves the worst case is a win here: submission is one draw, and the score is wherever that draw
# lands.  So the reader for this reports per-arm min/median/max across replicates and ranks on the
# worst, not the average.
#
# Three replicates per arm is thin for a spread estimate and is what fits -- 240 s runs cost 4x,
# and the four instances span the range b240 covered (P16 unstable at 16.2%, P6 4.1%, P20 2.5%,
# P1 0.65%), so an effect on variance should show up as the wide ones narrowing.
set -u
cd "$(dirname "$0")/.." || exit 1
echo r240 > harness/CURRENT
L=results/audit/r240.log
mkdir -p results/audit; touch $L

run(){ # rep R prob
    local tag="r$1.R$2.$3"
    grep -q "\[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    OGC_ROUNDS=$2 OGC_WSTAT=1 timeout 900 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/r240.log \
      && git commit -q -m "in-flight: r240 $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 16 6 20 1; do
        for R in 1 2 3; do
            run $rep $R $p
        done
    done
    echo "REPDONE $rep" >> $L
done
echo "R240DONE" >> $L
echo idle > harness/CURRENT

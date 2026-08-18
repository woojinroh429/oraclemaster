#!/bin/bash
# MCAND ON prob_1 AT 120 s -- THE ONE BUDGET IT HAS NEVER BEEN TRIED AT.
#
# Branching the dispatch order is the only structural change left: three exchange routes have now
# failed and all three held construction order fixed (bay_swap found no room, cprt's planned times
# are not packing-feasible, xswap could not leave the attractor set).  OGC_MCAND changes the order
# itself -- each beam state expands the M earliest UNPLACED blocks instead of only order[level], so
# states differ in WHICH blocks they hold.
#
# ON prob_1 IT IS MEASURED AND BAD, AT 60 s:
#
#     mwall.log, WORKERS=1, wall clock, medians of three
#     M=1  571,668      M=2  +26.3%      M=4  +33.4%      M=8  +24.6%
#
# The reason it loses on small instances is that branching costs levels and draws, and prob_1's
# beam FINISHES -- there is nothing to salvage, so the extra width buys nothing and the lost depth
# is pure cost.
#
# WHY 120 s IS NOT THE SAME QUESTION.  That cost is relative to the budget, and doubling it halves
# the weight of the loss.  cprt120 also showed prob_1 is a different regime at 120 s: the control
# returned 515,621 on six consecutive draws where at 60 s it spanned 508k-684k.  A knob whose whole
# failure mode is "it spends budget" deserves one look at the budget where spending is cheap, and
# that look has never been taken.
#
# WHAT WOULD MAKE IT FAIL, named first.  The 60 s losses are large -- 24-33%, not marginal -- and
# doubling the clock is unlikely to reverse a third of the objective.  The likeliest outcome is
# that M stays wrong on this instance and the shape rule MGATE already ships (fire only above
# peak_util 2.0, and prob_1 is 1.02) is confirmed as the right home for it.
#
# The control is deterministic at 120 s, so three draws per arm is enough to see anything real.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo m120 > harness/CURRENT
L=results/audit/m120.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/m120.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/m120.sh \
        && git commit -q -m "in-flight: m120 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" m="$2"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env OGC_MSET=$m timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for m in 1 2 4 8; do
    run "m.p1.$m.r$rep" $m
  done
done
echo "M120DONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# EVERYTHING TODAY WAS MEASURED AT 60 s AND THE BUDGET IS NOT 60 s.
#
# I took 60 from results/stage2/*.log, which every earlier run used, and never checked whether it
# was the competition budget.  The rules say the limit "can vary across problems" and that the
# limits for hidden problems "are disclosed only after the competition ends" -- so there is no
# single number to have found, and the technical report's own text refers to "331 s of a 180 s
# budget".  Earlier work used 180.  Today's 60 was the outlier and it was my assumption.
#
# It matters because the whole afternoon's chain is budget-dependent:
#
#   bandit    selection costs 1-9% against spending everything on one axis.  With 4x the budget
#             the bandit can afford to try all six properly and that toll should shrink.
#   orders    a single fixed order beat the six-axis portfolio on 3 of 4 -- same mechanism.
#   newaxis   sac3 measured -17% alone and diluted to -1.4% inside six axes, because five others
#             were taking their share of a small budget.
#   "six axes is too many"  rests entirely on the three above.
#
# So this asks the ONE question the rest hangs on, at 240 s: does a single order still beat the
# portfolio?  If it does not, the afternoon's direction dissolves and base is already right.  If
# it does, the direction survives a 4x budget and is worth the redesign.
#
# Arms are the two that bracket the claim -- the shipped six against the single order that won
# each instance at 60 s -- plus a4, since fewer-but-distinct axes is the shape the answer would
# take.  Four instances, two replicates: 240 s runs cost four times as much and the question is
# directional, not a final validation.
set -u
cd "$(dirname "$0")/.." || exit 1
echo b240 > harness/CURRENT
L=results/audit/b240.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 900 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/b240.log \
      && git commit -q -m "in-flight: b240 $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
    for p in 16 6 20 1; do
        run $rep base $p ""
        run $rep sac3 $p "OGC_ORDER=sac3"
        run $rep lst  $p "OGC_ORDER=lst"
        run $rep a4   $p "OGC_AXSET=a4"
    done
    echo "REPDONE $rep" >> $L
done
echo "B240DONE" >> $L
echo idle > harness/CURRENT

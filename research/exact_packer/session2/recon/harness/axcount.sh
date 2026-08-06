#!/bin/bash
# How many axes, and which viewpoints?  The count has never been measured in the region that
# matters.
#
# What is known: a single fixed order beat the shipped six on 3 of 4 instances (orders), and seven
# axes were 10.8% worse than six on P1 (newaxis v3).  So 1 > 6 > 7, and 4 and 5 are unmeasured.
# bandit priced the mechanism -- choosing among six costs 1-9% against spending the whole budget
# on one, because every axis takes a share of the draws and each draw gets shallower.
#
# One axis is not shippable.  P1 wants lst, P6 rank, P16 sac3, P20 the portfolio, and nothing
# readable off an instance separates them; that held through every experiment today.  So the
# question is where between 1 and 6 the trade turns, and the answer has to keep enough coverage
# for eight hidden instances whose types are unknown -- losing a viewpoint is a worse risk than
# paying some selection toll.
#
# The sets are built by VIEWPOINT rather than by trimming the current list, because four of its
# six slots hold the same viewpoint (three defer_big entries sort on due as their second key, and
# edd is that view again):
#
#   a4    lst, big_first, sac3, edd          slack / size / blend / deadline
#   a5    a4 + rank                          adds the blend without the sacrifice
#   a5d   lst, big_first, sac3, rank, defer_big
#                                            swaps edd for defer_big -- which deadline form earns
#                                            the slot?  defer_big holds three slots today and was
#                                            best on nothing.
#   base  the shipped six
#
# Eight instances and three replicates, same as newaxis, so the logs compare directly.  Runs after
# newaxis: that one decides what belongs in six slots, this one whether six is the right number,
# and reading them together needs both.
set -u
cd "$(dirname "$0")/.." || exit 1
echo axcount > harness/CURRENT
L=results/audit/axcount.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -q "\[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/axcount.log \
      && git commit -q -m "in-flight: axcount $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 1 12 16 26 6 3 20 30; do
        run $rep base $p ""
        run $rep a4   $p "OGC_AXSET=a4"
        run $rep a5   $p "OGC_AXSET=a5"
        run $rep a5d  $p "OGC_AXSET=a5d"
    done
    echo "REPDONE $rep" >> $L
done
echo "AXCOUNTDONE" >> $L
echo idle > harness/CURRENT

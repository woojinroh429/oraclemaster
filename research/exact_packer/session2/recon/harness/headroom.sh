#!/bin/bash
# IS THE ANSWER SLOW TO FIND, OR OUT OF REACH?  Everything else depends on which.
#
# A rival reports 2.40M on hidden prob_1.  Our five submitted draws there are 2,847,060 /
# 2,875,074 / 3,062,061 / 3,068,862 / 3,328,237 -- the BEST of them is 18.6% above, the median
# 27.5%.  That is not draw luck.  Something reachable to someone else is not in our reachable set,
# and the levers this session has measured have a combined range of about 2%:
#
#     budget reallocation (ROUNDS, redraw, aim race)   all lost
#     axis-set replacement (ortho)                     3 of 6 double-digit losses
#     w3mul grid                                       raising it is worse
#     brk removal                                      neutral, confirmed on the hidden set
#     five submitted totals                            1.4% band, 1.33% of it from identical code
#
# So the question is not how to divide the budget.  It is whether 240 s is short of what this
# search can do, or whether the search saturates well above what a rival reaches.
#
#   (A) a long run beats 240 s by a lot   -> the answer is reachable and we are slow.  Speed,
#                                            selection and scheduling all become worth doing.
#   (B) a long run beats 240 s by little  -> the search is converged and the gap is a DIFFERENT
#                                            KIND of solution.  Every axis, budget and operator
#                                            experiment this session was on the wrong axis, and
#                                            construction has to change.
#
# cliff40 saw both shapes and never went past 300 s: prob_40 was flat from 60 s, prob_34 improved
# 12% from 60 s to 240 s.  15x the budget has never been tried.
#
# data/hidden is gone from disk (untracked, lost in a container restart), so the rival's instance
# cannot be run.  These are stage-2 instances, chosen to span size: prob_20 (250 blocks),
# prob_13 (300, tardiness-dominated), prob_1 (150, the smallest and the most likely to saturate).
# Instance-major so the first complete curve arrives in ~84 minutes rather than at the end.
set -u
cd "$(dirname "$0")/.." || exit 1
echo headroom > harness/CURRENT
L=results/audit/headroom.log
mkdir -p results/audit; touch $L

run(){ # prob secs
    local tag="h.$1.$2"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_WSTAT=1 timeout $(( $2 * 2 + 600 )) /usr/bin/python3.12 harness/run1.py myalgorithm $1 $2 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$1 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/headroom.log \
      && git commit -q -m "in-flight: headroom $tag" ) >/dev/null 2>&1
}

for p in 20 13 1; do
    for T in 240 1200 3600; do
        run $p $T
    done
    echo "CURVEDONE $p" >> $L
done
echo "HEADROOMDONE" >> $L
echo idle > harness/CURRENT

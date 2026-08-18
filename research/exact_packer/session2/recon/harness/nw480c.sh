#!/bin/bash
# 480 s IS WHERE THE SHIPPED DEFAULT LOOKS WRONG, AND IT IS THE BUDGET THAT MATTERS MOST.
#
# nw = cpu - 1 shipped on "the worst draw improves in all six cells", measured at 60 / 120 / 240 s.
# The 480 s cells do not agree, and they disagree the same way on BOTH instances:
#
#                    worst      w4 span -> w3 span
#     prob_1  480 s  +3.12%      9.1% -> 16.2%
#     prob_16 480 s  +3.73%      7.7% -> 24.0%
#
# Five cells below 480 s: w3 tighter in every one, worst better in every one, by 6.1% to 18.7%.
# Two cells at 480 s: w3 wider in both, worst worse in both.  A clean split by budget, not noise
# scattered across cells -- which is what makes it worth finishing rather than dismissing.
#
# AND IT LANDS EXACTLY WHERE IT COSTS.  friend_ref/README.md records the reference submission
# running close to the full ~500 s budget, so the instances scored at this budget carry the points.
# An arm that trades a better tail below 240 s for a worse one at 480 s is a bad trade for this
# submission specifically.
#
# THE EXPLANATION OFFERED EARLIER IS WITHDRAWN.  prob_1 saturates by 240 s and prob_16 does not --
# w4 kept finding new instance bests at 480 s -- so "the gain lives where the search is starved"
# predicted w3 winning prob_16 at 480 s.  It lost.  Saturation is not the mechanism.
#
# WHAT REMAINS UNEXPLAINED, and is the reason for more draws rather than a theory: at 480 s w3 is
# the WIDER arm on both instances, which is the opposite of every shorter budget.  A minimum over
# three should not become noisier than a minimum over four as the budget grows -- both arms get
# more rounds, so both should settle.  Either the 480 s cells are underpowered at n=2-3, or
# something about the long-budget round structure differs by worker count.  Five pairs decide
# which question is even worth asking.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nw480c > harness/CURRENT
L=results/audit/nw480.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nw480.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nw480c.sh \
        && git commit -q -m "in-flight: nw480c $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 2 + 120 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 3 4 5; do
  run "b480.r$rep.p16.w4" 16 480 "WORKERS=4"
  run "b480.r$rep.p16.w3" 16 480 "WORKERS=3"
done
echo "NW480CDONE" >> $L
echo idle > harness/CURRENT

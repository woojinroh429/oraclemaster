#!/bin/bash
# FINISH BOTH 480 s CELLS.  THIS IS THE BUDGET THE SHIPPED DEFAULT LOOKS WRONG AT.
#
# nw = cpu - 1 shipped on "the worst draw improves in all six cells", measured at 60 / 120 / 240 s.
# The two 480 s cells disagree, and they disagree the SAME WAY on both instances:
#
#                    worst      w4 span -> w3 span     n
#     prob_1  480 s  +3.12%      9.1% -> 16.2%         3
#     prob_16 480 s  +3.73%      7.7% -> 24.0%         2
#
# Five cells below 480 s: w3 tighter in all five, worst better in all five, by 6.1% to 18.7%.
# Two cells at 480 s: w3 wider in both, worst worse in both.  That is a split by budget, not noise
# scattered at random -- which is why it gets finished rather than dismissed.
#
# AND IT LANDS EXACTLY WHERE IT COSTS.  friend_ref/README.md records the reference submission
# running close to the full ~500 s budget, so the instances scored there carry the points.  An arm
# that buys a better tail below 240 s and sells one at 480 s is a bad trade for this submission.
#
# THE EXPLANATION OFFERED EARLIER IS WITHDRAWN.  prob_1 saturates by 240 s and prob_16 does not --
# w4 kept setting new instance bests at 480 s -- so "the gain lives where the search is starved"
# predicted w3 winning prob_16 at 480 s.  It lost.  Saturation is not the mechanism.
#
# WHAT IS UNEXPLAINED, and the reason for draws rather than a theory: at 480 s w3 is the WIDER arm
# on both instances, the opposite of every shorter budget.  A minimum over three should not become
# noisier than a minimum over four as the budget grows; both arms get more rounds and both should
# settle.  Either these cells are underpowered at n=2-3, or the long-budget round structure differs
# by worker count.  Five pairs each decide which question is worth asking.
#
# Two earlier attempts to chain this work died with their parent shell, so both cells run here in
# one script.  prob_16 first: it is the cell with fewer draws and the larger disagreement.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nw480d > harness/CURRENT
L=results/audit/nw480.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nw480.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nw480d.sh \
        && git commit -q -m "in-flight: nw480d $1" \
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
echo "== NW480D prob_16 done ==" >> $L
for rep in 4 5; do
  run "b480.r$rep.p1.w4" 1 480 "WORKERS=4"
  run "b480.r$rep.p1.w3" 1 480 "WORKERS=3"
done
echo "NW480DDONE" >> $L
echo idle > harness/CURRENT

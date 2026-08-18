#!/bin/bash
# SPREAD THE FOUR WORKERS ACROSS THE AIM RANGE INSTEAD OF STACKING THEM ON ITS TWO ENDS.
#
# aim is the fraction of its slice a beam may spend, and it becomes width directly
# (left = budget*AIM - elapsed, Bcur = left/(per*rem)).  The shipped default is OGC_AIMSET
# "0.90,0.10" indexed by wid % 2, so two workers run deep and two run shallow with NOTHING in
# between.  Measured on real runs, those two populations are far apart:
#
#     aim 0.90   level=1.00   3,258-9,666 expansions
#     aim 0.10   level=0.13-0.38   41-115 expansions, the rest filled by greedy rollout
#
# aimsplit rep1 says neither end can be dropped.  Against base, all-deep and all-shallow:
#
#            deep      shal
#     P16  -11.5%    - 3.1%
#     P1   - 6.2%    +49.9%      removing the deep workers is catastrophic here
#     P20  +13.9%    - 0.5%      removing the shallow workers is catastrophic here
#     P4   - 0.96%   + 4.47%
#     P6   - 0.73%   - 1.16%
#
# So both ends are load-bearing and the useful depth is instance-specific.  If that is right, the
# middle of the range is worth covering and currently nobody looks there.
#
# WHAT IT COSTS, stated up front: today each end has TWO workers, so the answer is a min over two
# draws at that depth.  Spreading gives each depth ONE.  On prob_1, where deep is clearly right,
# trading a second deep worker for a 0.60 and a 0.30 could lose more than the coverage gains.  The
# data does not say -- it establishes that both ends matter, not that the middle helps.
#
# The tree's own comment anticipated this arm: "the alternative -- spreading the four workers
# across the range instead of stacking them on its two ends -- is one env away and can be measured
# instead of argued about."
#
# JUDGED ON THE WORST INSTANCE, NOT THE MEAN.  What base buys is that it is never catastrophic;
# an arm with a better average and a +50% instance is a worse thing to ship on a per-instance
# score.
#
# Instance-major so a full five-instance comparison exists after one pass.
set -u
cd "$(dirname "$0")/.." || exit 1
echo spreadaim > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=spreadaim" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/spreadaim.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob aimset
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_AIMSET="$4" OGC_WSTAT=1 timeout 1200 \
        /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 "[$tag]" --data data/stage2 \
        >> $L 2>&1 || echo "P$3 [$tag] CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/spreadaim.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: spreadaim $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
  for p in 16 1 20 4 6; do
    run $rep base   $p "0.90,0.10"
    run $rep spread $p "0.90,0.60,0.30,0.10"
  done
  echo "REPDONE $rep" >> $L
done
echo "SPREADAIMDONE" >> $L
echo idle > harness/CURRENT

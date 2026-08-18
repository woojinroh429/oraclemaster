#!/bin/bash
# RUN BOTH m VALUES AND LET THE MINIMUM PICK.  Three arms, one code, one binary.
#
# OGC_MCAND decides how many candidate blocks each beam state expands, and its sign varies by
# instance at 240 s:
#
#     P24  2,695,530 -> 2,454,698  -8.93%      P4   2,679,086 -> 2,840,189  +6.01%
#     P20  9,459,219 -> 8,868,533  -6.25%      P1     544,247 ->   693,845 +27.49%
#
# Neither value is a default.  But the answer is a MINIMUM over four worker processes, so both
# values can be in the portfolio and the min keeps whichever this instance prefers -- the same
# construction the beam aim already uses at 2:2.
#
# WHY IT MIGHT STILL FAIL, measured rather than guessed.  A 2:2 split draws twice from each setting
# instead of four times, and a minimum over two is worse than a minimum over four, so the split can
# land BELOW both parents.  That is not hypothetical: the identical split applied to the hz1
# lookahead was the best of three arms on P16 and P20 and worse than BOTH parents on P6.  The whole
# question is whether the diversity buys more than the density costs, on this knob.
#
# ALL THREE ARMS ARE RE-RUN.  The m1 and m2 cells already in mcand.log were taken before OGC_MSET
# was added to the worker, and unused code in that function has moved an objective by 1.03% on this
# project before -- so they are not a valid baseline for the split and are not reused.
#
# Four instances, chosen as two of each sign: prob_24 and prob_20 where m=2 wins, prob_1 and prob_4
# where it loses.  A split that only helps where m=2 already helps is worth nothing.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo mset > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=mset" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/mset.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/mset.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: mset $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# Arms adjacent within an instance so machine drift cannot be read as an arm difference.
for p in 24 20 1 4; do
  run "s240.p$p.m1"  $p 240 "OGC_MCAND=1"
  run "s240.p$p.m2"  $p 240 "OGC_MCAND=2"
  run "s240.p$p.mix" $p 240 "OGC_MSET=1,2"
done
echo "== MSET pass 1 done ==" >> $L

# A second pass on the same four, because every arm difference here has to clear a spread that runs
# to 9% on prob_20 and 15% on prob_1.
for p in 24 20 1 4; do
  run "s240.p$p.m1.r2"  $p 240 "OGC_MCAND=1"
  run "s240.p$p.m2.r2"  $p 240 "OGC_MCAND=2"
  run "s240.p$p.mix.r2" $p 240 "OGC_MSET=1,2"
done
echo "MSETDONE" >> $L
echo idle > harness/CURRENT

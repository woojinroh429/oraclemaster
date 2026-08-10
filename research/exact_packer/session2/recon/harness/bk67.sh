#!/bin/bash
# DOES THE (B, K) STRUCTURE SURVIVE THE TRIP FROM THE SEED TO THE ANSWER?
#
# THE STRUCTURE.  Deterministic, digest-verified, at work 3,000, on two instances from two
# objective families (prob_1 is 86.3% Z3, prob_16 is 48.7%):
#
#     prob_1                            prob_16
#     axis 2  67/5     684,687          axis 2  67/5   3,190,472
#     axis 3  67/5     737,578          axis 3  67/5   4,684,351
#     axis 0  96/4   1,174,681          axis 5  48/6   6,610,637
#     axis 1  96/4   1,323,041          axis 0  96/4   6,671,345
#     axis 5  48/6   1,350,271          axis 1  96/4   6,720,274
#     axis 4  96/3   1,403,609          axis 4  96/3   9,382,627
#
# The two 67/5 axes are first and second on BOTH, and on prob_1 the ordering holds at all four
# work levels tested.  They differ from each other in order (lst vs edd), pos_lam (0.15 vs 0.05),
# fut_beta (0.0 vs 1.5) and w3mul (3.0 vs 1.0), so what they share that wins is the width and the
# branching factor and not the fields the axis table was designed around.
#
# OGC_AXSET=bk67 gives every axis Bmul 0.7 and K 5 and changes NOTHING else.  All six keep their
# orders and weights, so the portfolio stays a portfolio -- which is the difference from the 7th
# submission's global order=lst + w3mul=0.5, which rewrote every axis and lost 14-19% on P2, P5
# and P8 by deleting the alternatives.
#
# WHY THIS MIGHT STILL FAIL, STATED FIRST.  Pinned axis 2 -- which already IS 67/5 -- finished at
# 515,465 in the wall-clock sweep, sixth of seven, while the rotation finished at 461,233.  Seed
# quality did not carry to the answer there.  The difference bk67 is betting on is that pinning
# destroyed the portfolio while this keeps it: six orders, one width.  If bk67 loses anyway, then
# width is a seed property that the operators wash out, and the deterministic table -- however
# clean -- does not reach the score.  That is worth knowing and it is the likeliest outcome given
# how tonight has gone.
#
# THE NOISE IS THE REASON FOR THE REPLICATE COUNTS.  prob_1's controls span 422,629 to 499,210 in
# this build, so three pairs is the minimum that has ever changed my mind about it, and even three
# has reversed on me once.  prob_16 and prob_20 get two.  Nothing under about 8% will be readable
# and that is stated in advance rather than discovered afterwards.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo bk67 > harness/CURRENT
L=results/audit/bk67.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/bk67.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: bk67 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  run "r$rep.p1.base" 1 240 ""
  run "r$rep.p1.bk67" 1 240 "OGC_AXSET=bk67"
done
echo "== BK67 prob_1 done ==" >> $L

for rep in 1 2; do
  for p in 16 20; do
    run "r$rep.p$p.base" $p 240 ""
    run "r$rep.p$p.bk67" $p 240 "OGC_AXSET=bk67"
  done
done
echo "BK67DONE" >> $L
echo idle > harness/CURRENT

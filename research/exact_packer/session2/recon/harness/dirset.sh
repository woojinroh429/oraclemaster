#!/bin/bash
# THE 7TH SUBMISSION'S DIRECTION, PUT WHERE IT COSTS NOTHING.
#
# WHY P1 AND P3 IMPROVED, WHICH IS NOT NOISE.  The 7th entry shipped order=lst + w3mul=0.5 +
# resfrac=0.50 as a global override and scored, against the 6th:
#
#     inst   6th objective        delta
#     P6      1,049,207          -7.06%
#     P1      2,883,654          -6.86%     best-ever on this instance
#     P4      4,372,076          +2.67%
#     P3      5,715,679          -2.55%     best-ever on this instance
#     P5      6,059,733         +19.03%
#     P7     16,074,005          +5.41%
#     P8     17,337,659         +14.00%
#     P2     19,785,239         +14.23%
#
# Ordered by the instance's own objective the deltas are almost monotone, and the two exceptions
# (P3 and P5) are adjacent in size.  That is a mechanism, not a coincidence:
#
#   w3mul=0.5 tells the beam to chase preferred bays LESS while constructing and leaves the
#   preference to z3_reassign afterwards.  That pass moves a block only to a MORE preferred bay,
#   and only when w1*dtardy + w3*dpen < 0 -- so it needs the destination to be free at the block's
#   window.  A loose yard has room, the trade pays, and construction is better for not having
#   fought for preference early.  A saturated yard has none: the polish collects nothing and the
#   construction was weakened for free.  A large objective is what a saturated yard looks like.
#
# So the direction is right on part of the set and wrong on the rest, which is a PORTFOLIO POSITION
# -- and this one is free.  The aim and m splits both index by wid % 2, so they are correlated
# rather than crossed and the four workers hold two configurations, two workers each.  Hanging a
# third knob on the same parity does not create a third configuration; it makes the two that exist
# further apart.  No slot is spent, the pair-at-each-end guarantee is untouched.
#
#     workers 0,2   aim 0.90  m=1  default order/w3mul
#     workers 1,3   aim 0.10  m=2  order=lst  w3mul=0.5
#
# resfrac is left out on purpose: it is set once in algorithm() and cannot be split per worker, and
# halving the beam's budget on every instance is the part of the 7th with no upside anywhere.
#
# WHAT THE QUEUE HAS TO SHOW.  The direction must not cost anything on the instances the 7th lost
# -- if a worker split reproduces the +14-19% it is worthless, and the whole claim is that it
# cannot, because those workers' answers are discarded by the minimum.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo dirset > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=dirset" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/dirset.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/dirset.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: dirset $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_1 is the loose one this should help (peak occupancy 59.3% of bay area, 73% of its objective
# in Z3) and prob_6, prob_36 and prob_20 are the saturated ones it must not hurt.  prob_16 and
# prob_24 sit between.  Arms adjacent so machine drift is not read as an arm difference.
for p in 1 6 20 16 24 36; do
  run "d240.p$p.base" $p 240 ""
  run "d240.p$p.dir"  $p 240 "OGC_DIRSET=1"
done
echo "== DIRSET pass 1 done ==" >> $L

for p in 1 6 20 16 24 36; do
  run "d240.p$p.base.r2" $p 240 ""
  run "d240.p$p.dir.r2"  $p 240 "OGC_DIRSET=1"
done
echo "DIRSETDONE" >> $L
echo idle > harness/CURRENT

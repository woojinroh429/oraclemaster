#!/bin/bash
# DOES THE BRANCHING WIN GENERALISE, AND WHERE IS THE THRESHOLD.
#
# mwall.log, wall clock, three draws, medians against M=1:
#
#     P13  300 blk / 2 bay  pu 4.09     M=2 -5.1%   M=4 -6.6%   M=8 -15.5%
#     P16  300 blk / 5 bay  pu 1.23         +16.4%      +34.1%       +5.7%
#     P3   200 blk / 4 bay  pu 1.18         + 6.3%      + 4.5%       +2.8%
#     P1   150 blk / 3 bay  pu 1.02         +26.3%      +33.4%      +24.6%
#
# One instance wants branching and it is the crowded one.  The reading is that where the yard is
# saturated, WHICH block goes next decides the layout, and where it is not, depth decides it and
# branching only costs draws.
#
# BUT IT IS ONE INSTANCE.  P13 is 300 blocks in 2 bays -- and so are P36 (pu 4.66) and P25 (6.26),
# which were never swept.  If they agree, the rule is a family and a threshold can be placed.  If
# they do not, P13 is a single point and this is the same overfit that was rejected nine times
# today.
#
# P2 (250 blk / 3 bay, pu 3.29) is the middle: it decides whether the cut sits near 2 or near 4.
# P39 (pu 3.79) brackets it from above.
#
# WHAT WOULD MAKE IT FAIL, named first.  P25 floors at everything except nw=1 (nwsize.log), so its
# M cells may all come back at 4,255,755,887 and say nothing about branching at all.  That is why
# WORKERS=1 is used here -- it is the only setting where P25 produces a real answer -- and why P25's
# result must be read as "does M help a single worker on a crowded instance", not as a shipping
# configuration.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo mrule > harness/CURRENT
L=results/audit/mrule.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/mrule.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/mrule.sh \
        && git commit -q -m "in-flight: mrule $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" m="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env WORKERS=1 OGC_MCAND=$m timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2; do
  for p in 36 25 2 39; do
    for m in 1 4 8; do
      run "r.p$p.m$m.r$rep" $p $m
    done
  done
done
echo "MRULEDONE" >> $L
echo idle > harness/CURRENT

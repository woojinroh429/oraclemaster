#!/bin/bash
# PHASE 2: WHAT M COSTS ON THE CLOCK, WHICH IS THE BUDGET THE COMPETITION ACTUALLY GIVES.
#
# mcand.log settled quality per unit of WORK, deterministically:
#
#                          M=1        M=2     M=3     M=4     M=6     M=8
#     P1  150 blk / 3 bay     492,458  +42.6%  +56.0%  +80.8%  +73.1%  +54.8%
#     P3  200 blk / 4 bay   4,367,826  + 4.7%  +16.0%  +11.0%  + 8.8%  +15.1%
#     P16 300 blk / 5 bay   3,097,236  + 1.3%  +13.7%  +27.0%  +41.2%  +57.6%
#     P13 300 blk / 2 bay  88,534,512  + 0.9%  + 0.1%  - 0.5%  - 3.7%  - 9.5%
#
# `work += nbeam*M` per level, so at a fixed work cap a larger M reaches fewer levels -- that is the
# trade phase 1 priced.  On the clock the trade is different: the beam runs every level at any M and
# simply takes longer per call, so M buys per-draw quality and pays in DRAWS PER RUN.  Those are not
# the same exchange rate, and ogc_fast.cpp says so where it defines WORKCAP: "equal-work A/B ...
# throughput ... combine: quality at work = throughput x 240".
#
# This is the throughput half.  No WORKCAP, real 60 s, everything else as phase 1 (WORKERS=1 so M is
# unambiguous).  Three draws because the clock puts the noise back -- 17-35% run to run is what every
# wall-clock experiment today had to carry.
#
# WHAT WOULD MAKE PHASE 1's ANSWER SURVIVE: if P13 still prefers a large M here, the shape rule is
# real and shippable.  WHAT WOULD KILL IT: if the lost draws cost more than the better draws buy,
# P13's -9.5% at equal work becomes a loss at equal seconds and M stays where it is.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo mwall > harness/CURRENT
L=results/audit/mwall.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/mwall.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/mwall.sh \
        && git commit -q -m "in-flight: mwall $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" m="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env WORKERS=1 OGC_MCAND=$m timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
# P13 first: it is the instance the shape rule would fire on, so it decides the arm.
for rep in 1 2 3; do
  for p in 13 1 16 3; do
    for m in 1 2 4 8; do
      run "w.p$p.m$m.r$rep" $p $m
    done
  done
done
echo "MWALLDONE" >> $L
echo idle > harness/CURRENT

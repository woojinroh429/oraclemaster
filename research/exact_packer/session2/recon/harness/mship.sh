#!/bin/bash
# TWO THINGS BEFORE A SHAPE RULE CAN SHIP: WHERE THE CUT GOES, AND WHETHER IT SURVIVES nw=3.
#
# mrule.log + mwall.log, wall clock, WORKERS=1, medians against M=1:
#
#     P25  pu 6.26   M=4 - 3.0%   M=8 - 9.4%
#     P36  pu 4.66       - 8.0%       -17.5%
#     P13  pu 4.09       - 6.6%       -15.5%
#     P39  pu 3.79       - 5.6%       - 3.8%
#     P2   pu 3.29       -16.2%       -17.3%
#     ------------------------------------------
#     P16  pu 1.23       +34.1%       + 5.7%
#     P3   pu 1.18       + 4.5%       + 2.8%
#     P1   pu 1.02       +33.4%       +24.6%
#
# Five for five above 3.29, three for three below 1.23, and nothing measured between.  That gap is
# where the threshold has to sit and it is currently guesswork.
#
# ARM A -- THE UNTESTED BAND.  P23 (2.79) and P11 (2.14) decide whether the cut can go at 2.0, which
# would fire on 16 of the 40 practice instances, or has to sit at 3.0 and fire on 5.
#
# ARM B -- THE SHIPPED WORKER COUNT.  Every M cell so far is WORKERS=1.  What ships is nw=3 with
# OGC_MSET indexed by wid%2, and nwsize.log already showed the pool path behaves differently enough
# to floor P25 entirely.  A rule measured only at nw=1 is not a rule that can be shipped.  This runs
# the shipped worker count with MSET pinned to a single value, so "all workers M=1" and "all workers
# M=8" are compared on the configuration the grader will use.
#
# WHAT WOULD MAKE IT FAIL, named first.  At nw=3 the portfolio already spends one worker on M=2, so
# part of branching's value may already be collected and the marginal gain from pinning M=8 could be
# far smaller than the WORKERS=1 numbers suggest.  And P25 floors at nw=3 regardless of M, so its
# arm-B cells will say nothing.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo mship > harness/CURRENT
L=results/audit/mship.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/mship.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/mship.sh \
        && git commit -q -m "in-flight: mship $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" envs="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $envs timeout 200 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
# ARM A: the untested band, single worker, matching the sweeps above
for rep in 1 2; do
  for p in 23 11; do
    run "a.p$p.m1.r$rep" $p "WORKERS=1 OGC_MCAND=1"
    run "a.p$p.m8.r$rep" $p "WORKERS=1 OGC_MCAND=8"
  done
done
# ARM B: the shipped worker count, MSET pinned so every worker takes the same M
for rep in 1 2 3; do
  for p in 13 2 36 1 3 16; do
    run "b.p$p.s1.r$rep" $p "OGC_MSET=1"
    run "b.p$p.s8.r$rep" $p "OGC_MSET=8"
  done
done
echo "MSHIPDONE" >> $L
echo idle > harness/CURRENT

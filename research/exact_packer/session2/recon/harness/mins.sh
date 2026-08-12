#!/bin/bash
# INSURANCE AGAINST THE FLOOR, PAID IN PORTFOLIO DIVERSITY RATHER THAN WALL CLOCK.
#
# THE FAILURE.  When no worker returns, algorithm() falls through to _safe_sequential.  On stage-2
# prob_13 at 60 s that is 4,027,473,504 against the 68,921,195 a completed round returns -- FIFTY
# -EIGHT TIMES WORSE, silently, feas=y.  Counted across today's runs at a 60 s limit:
#
#     WORKERS=7   floored 2 of 2   (both idle60 arms, A and C alike)
#     shipped nw  floored 1 of 10
#
# It did not happen in the submission that scored 72,188,856 -- a floored instance would have put
# the total above 4e9 on its own and the total was 7.2e7 -- but removing the CPU cap moves the
# shipped configuration toward the worker count where it floored every time.
#
# THE CAUSE, measured directly.  MGATE sets MSET=8 on saturated instances (prob_13 peak_util 4.089,
# prob_2 3.289), and each beam state then expands eight blocks instead of one.  The worker is
# granted _rb = 38 s and needs about 59 -- it overruns its own budget by ~55% -- so whether it
# lands before the collector's deadline is a coin flip under load.  The gate's own comment predicted
# exactly this: "an instance that finished comfortably at M=1 may not finish at all."
#
# TWO FIXES WERE TRIED AND REVERTED THIS HOUR, recorded so they are not retried.  Bounding the
# round's wait at _rb + 8 s cut healthy draws -- prob_13 fell from n=3 to n=1 on every replicate,
# because the workers genuinely need the full remaining clock.  And retrying in-process with M=1
# when a round came back empty ran to WALL 99.8 s on a 60 s limit, because an in-process worker has
# no pool to kill it.  Both made things worse and neither is in the file.
#
# THIS ONE CHANGES NO TIMING AT ALL.  OGC_MSET is a comma list indexed by wid % len (line 3196),
# so "8,1" hands half the pool M=8 and half M=1 through machinery that already exists.  The M=1
# draws are the configuration the gate itself calls comfortable, so at least one worker is near
# -certain to return and the pool cannot come back empty.
#
# WHAT IT COSTS AND WHAT WOULD MAKE IT FAIL, named first.  MGATE was adopted on 16 instances with
# 14 wins, all at MSET=8 for every worker; halving the M=8 draws should give back part of that
# gain, and if it gives back all of it the insurance is not worth buying at this price.  The other
# risk is PARROUND: after round 0 the pool commits nw-1 workers to the parity that won, so if M=8
# wins round 0 the insurance thins to one worker in three for the rest of the run -- still present,
# but thinner than the headline "half" suggests.
#
# ARMS: 8 is MGATE as it ships.  81 is MSET="8,1".  1 is MGATE off entirely, as the floor of
# comparison.  prob_13 and prob_2 are the two instances measured to floor; prob_36 is the instance
# MGATE was tuned on and is where the cost should show up worst if it shows up anywhere.
#
# JUDGED, fixed before the run: floor count first -- any arm that floors is beaten by any arm that
# does not, whatever the means are.  Quality second, paired ratio within replicate.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire mins
L=results/audit/mins.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/mins.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/mins.sh \
        && git commit -q -m "in-flight: mins $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" env0="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 13 2 36; do
    run "m8.p$p.r$rep"  $p "OGC_MGATE=1"
    run "m81.p$p.r$rep" $p "OGC_MSET=8,1"
    run "m1.p$p.r$rep"  $p "OGC_MGATE=0"
  done
done
echo "MINSDONE" >> $L
lock_release mins

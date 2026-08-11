#!/bin/bash
# THE timelimit <= 60 CONDITION RESTS ON ONE INSTANCE, AND IT MAY BE KEEPING THE GATE SHUT.
#
# The dirgate submission scored:
#
#     P1  3,051,204 -> 2,796,931  -8.33%      P2  +1.42%   P3  +6.93%   P4  +4.39%
#     P8 17,765,344 -> 16,960,384 -4.53%      P5  +2.53%   P6  +0.64%   P7  +1.08%
#     total 72,081,832 -> 72,188,856          +0.15%
#
# P1 is the best it has been since the 7th entry.  But myalgorithm.py records that IDENTICAL code
# resubmitted moved median -0.07% with a range of -5.16%..+8.66%, and every delta above sits inside
# that band -- so this submission attributes nothing, in either direction.
#
# Worse, it may not have tested the gate at all.  DIRGATE fires only when peak_util is in
# [1.00, 1.30] AND timelimit <= 60, and the hidden set's actual limits are unknown.  If they exceed
# 60 s the gate never opened and P1's -8.33% was a draw.
#
# THAT CONDITION CAME FROM prob_1 ALONE.  Three replicates each:
#
#      60 s   off 704,255 (spread 0.6%)   on 595,000   -15.5%, 3-0, distributions disjoint
#     120 s   off 492,989 (spread 1.9%)   on 513,703    +4.2%, 1-2, on-arm spans 33%
#
# One instance, and the 120 s arm's own spread is a third of its value.  The other five instances
# the gate fires on -- P3, P7, P16, P27, P33 -- have never been run at 120 s either way.  If they
# win there, the budget condition can be relaxed and the gate would actually engage on a hidden set
# that gives its instances more than a minute.  If they lose, the condition is right and the gate
# is correctly narrow, which is worth knowing before spending another submission on it.
#
# WHAT WOULD MAKE IT FAIL, named first.  These are single pairs on instances whose controls span
# 5-40%, so only a consistent SIGN across five instances means anything; one or two going either
# way is noise.  The rule fixed here before the run: relax the condition only if at least four of
# the five go the same way as the 60 s result, and treat three-two as no evidence.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo gate120 > harness/CURRENT
L=results/audit/gate120.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/gate120.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/gate120.sh \
        && git commit -q -m "in-flight: gate120 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 420 /usr/bin/python3.12 harness/run1.py myalgorithm $2 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# OGC_DIRGATET=999 lets the gate fire at 120 s; DIRGATE=0 is the control.
for rep in 1 2; do
  for p in 3 27 33 16 7; do
    run "g120.p$p.off.r$rep" $p "WORKERS=4 OGC_DIRGATE=0"
    run "g120.p$p.on.r$rep"  $p "WORKERS=4 OGC_DIRGATET=999"
  done
done
echo "GATE120DONE" >> $L
echo idle > harness/CURRENT

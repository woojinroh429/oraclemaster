#!/bin/bash
# DOES THE END MARGIN I JUST SHIPPED BUY ITS SAFETY WITH THE 58x FLOOR?
#
# THIS CHECKS MY OWN VERDICT AND IT MAY OVERTURN IT.  endpad.sh named exactly this kill condition
# -- "if ENDPAD 3 or 5 floors an instance that ENDPAD 1 did not, the margin is being bought with
# the exact catastrophe it was meant to prevent" -- and I cleared it on 18 cells per arm aggregated
# over six instances, which gave 1 floor per arm.  Checking prob_13 alone gave 1 of 3 per arm and
# I called that even.  Three cells per arm on a rare event is not a measurement of a rate.
#
# cpufill THEN RAN prob_13 TWELVE TIMES WITH ENDPAD 5 AS THE SHIPPED DEFAULT AND FLOORED 10 OF 12,
# including 4 of 4 at the shipped worker count.  Counting across every log today:
#
#     ENDPAD 1   (ffwall + mins + endpad e1)    1 floored of 18    6%
#     ENDPAD 5   (endpad e5 + cpufill w3)       5 floored of  7   71%
#
# THAT COMPARISON IS CONFOUNDED AND IS NOT EVIDENCE.  The two groups were taken hours apart under
# different box states, and prob_13's floor is a timing race, which is precisely the thing that
# drifts with load.  It is a reason to measure, not a finding.
#
# THE MECHANISM IS PLAUSIBLE, WHICH IS WHY IT CANNOT BE WAVED OFF.  wbudget = timelimit - reserve
# - elapsed - ENDPAD, so on prob_13 at 60 s the workers go from 38 s to 34 s.  prob_13 is the
# instance measured to need ~59 s when granted 38 -- it overruns its budget by ~55% and lands
# inside the collector's deadline only just.  Four seconds off the front is exactly the size of
# margin that decides that race.
#
# WHAT IS AT STAKE.  A floored prob_13 returns 4,027,473,504 against 68,921,195.  If ENDPAD 5
# raises that rate at all, it is trading a 2-second wall margin -- against an overrun that was
# measured at 60.6 s worst case, i.e. 1% over -- for a 5,800% loss.  That trade is never worth
# making, and ENDPAD would have to go back to 1 with the overrun accepted, or the overrun fixed
# somewhere that does not touch wbudget.
#
# PAIRED WITHIN REPLICATE, SAME RUN, INTERLEAVED, so the box state is shared rather than compared
# across hours.  Six replicates on prob_13 because a rate needs samples; prob_2 and prob_36 carry
# three each as the other two instances that have been seen to floor.
#
# JUDGED, fixed before the run: floor count per arm on prob_13 is the whole verdict.  If ENDPAD 5
# floors more than ENDPAD 1 by more than one cell, the default goes back to 1 and the wall overrun
# is accepted as the lesser failure.  Quality is not consulted -- a 58x event is not something a
# few per cent can offset.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire padfloor
L=results/audit/padfloor.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/padfloor.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/padfloor.sh \
        && git commit -q -m "in-flight: padfloor $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" ep="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_ENDPAD=$ep OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3 4 5 6; do
  for ep in 1 5; do
    run "e$ep.p13.r$rep" 13 $ep
  done
done
for rep in 1 2 3; do
  for p in 2 36; do
    for ep in 1 5; do
      run "e$ep.p$p.r$rep" $p $ep
    done
  done
done
echo "PADFLOORDONE" >> $L
lock_release padfloor

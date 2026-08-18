#!/bin/bash
# MORE DRAWS ON THE SAME FOUR CORES.  THE ONE LEVER THAT ATTACKS RUN-TO-RUN VARIANCE DIRECTLY.
#
# The user's problem is not the mean, it is the SPREAD: P1 has read 2,883,654 / 2,685,759 /
# 3,009,531 / 3,185,928 / 3,051,204 across five submissions -- an 18.6% band with no relationship
# to anything shipped in between.  A submission is one run, and the score is min-over-workers, so
# what decides it is how many independent draws that min is taken over.
#
# Every arm tonight tried to make the draws BETTER.  This one makes them MORE NUMEROUS.  It is the
# only intervention that lowers the mean and the variance by the same mechanism: for a minimum
# over N samples, both fall as N rises, and they fall fastest when the left tail is heavy -- which
# is exactly this distribution (prob_1's 1,176 worker results have 456 distinct values with the
# top 20 covering 34%).
#
# THE COST IS REAL AND IS THE WHOLE QUESTION.  Four cores run four workers at full speed.  Six
# workers on four cores each get two thirds of a core, eight get half.  Each draw is therefore
# worse.  Whether min-of-8-worse beats min-of-4-better is a trade nobody here has ever measured --
# harness/draws.sh has the w4/w6/w8 arms written and its w-section never ran.
#
# A SECOND THING w6 BUYS, from draws.sh's own comment: worker wid opens on _AXES[(wid+1) % 6], so
# with four workers axes 5 and 0 NEVER open a run.  Six workers is the first time all six axes get
# an opening slot.
#
# WHAT IS REPORTED.  Not the mean alone.  For each arm: the mean, the WORST cell, and the span --
# because on a per-instance score the worst run is what sets the tier, and reducing the span is
# the stated goal.  Five replicates per arm, which is thin for a variance estimate and is stated
# as such rather than discovered later; n=2 spreads misled me three times tonight.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nw > harness/CURRENT
L=results/audit/nw.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nw.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: nw $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4 5; do
  run "r$rep.p1.w4" 1 120 "WORKERS=4"
  run "r$rep.p1.w6" 1 120 "WORKERS=6"
  run "r$rep.p1.w8" 1 120 "WORKERS=8"
done
echo "== NW prob_1 done ==" >> $L

for rep in 1 2 3 4; do
  run "r$rep.p16.w4" 16 120 "WORKERS=4"
  run "r$rep.p16.w6" 16 120 "WORKERS=6"
  run "r$rep.p16.w8" 16 120 "WORKERS=8"
done
echo "== NW prob_16 done ==" >> $L

# The budget is not established, so the winner is re-checked at the other one before anything ships.
for rep in 1 2 3; do
  run "r$rep.p1L.w4" 1 240 "WORKERS=4"
  run "r$rep.p1L.w6" 1 240 "WORKERS=6"
done
echo "NWDONE" >> $L
echo idle > harness/CURRENT

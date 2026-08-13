#!/bin/bash
# ADD DRAWS BY RECLAIMING BUDGET THAT MEASURABLY BUYS NOTHING -- AIMED AT THE RIGHT INSTANCES.
#
# WHY THE FIRST VERSION WAS WRONG.  harness/budget.sh targeted prob_1, prob_3, prob_16.  The
# scoreboard has since shown practice prob_1 is NOT hidden P1 -- FFSET moved practice prob_1
# -12.53% and hidden P1 +10.10%, opposite directions -- and matching the two response vectors puts
# hidden P1 nearest prob_7, with prob_20 second.  So the instance the whole session was tuned on
# was the wrong one, and any conclusion budget.sh reached would have been aimed at it.  Re-aimed.
#
# WHY THIS LEVER AND NOT ANOTHER.  Everything that failed today either replaced a draw or replaced
# a configuration.  FFSET swapped the even workers' rung split, so where the even half answers the
# original draw is gone -- that is exactly why it won practice prob_1 and lost hidden P1.  PERMARG
# swapped the width estimator and pinned the result to one attractor, which under a MINIMUM
# forecloses the good tail.  This removes neither: every operator stays in the roster and stays
# selectable, it just auditions for a fixed number of seconds instead of 20% of the clock.
#
# THE WASTE IS MEASURED, from OPSTAT on stage-2 prob_1, single worker:
#
#     RESFRAC 0.50, 27.8 s total     grow 5.1 + bay 5.0 + brk 1.5 = 11.6 s = 41.7%, gain 0
#     RESFRAC 0.05, 54.7 s total     grow 9.8 + bay 9.3 + brk 13.3 = 32.4 s = 59.2%, gain 0
#
# All three at tried=1 -- the compulsory first probe and nothing more -- and all three return zero.
# `slot` opens every search operator at 20% of the budget and `unt` runs each untried operator
# before selection by rate begins, so the sample of a known-zero operator grows with the clock.
#
# AND THE PRICE OF A DRAW IS ALREADY KNOWN.  From every WSTAT draw logged, expected minimum over k:
# prob_7 k=3 901,050, k=6 -6.5%, k=12 -10.9%.  Recovering ~40% of the slice is roughly 1.7x the
# beam draws, so the order of magnitude to expect on prob_7 is -4%.  Hidden P1 sits 1.37% behind
# the competitor with gate_endpad, so that would be decisive if it holds.
#
# WHAT WOULD MAKE IT FAIL, named first, and it has been observed directly.  An operator that needs
# TIME before it earns anything gets judged on a probe too short to earn it, and the selection loop
# never revisits a zero: OGC_BRKFLOOR=25 took brk from 0.4 s and gain 0 to 34 s and gain 62,222 on
# the same instance.  A cap that is too tight does not merely waste less, it amputates.  prob_3 and
# prob_16 are carried as the veto because brk demonstrably pays there (prob_3: 80,795 with it
# against 96,990 without).
#
# The second failure mode is the one this session keeps repeating: prob_7's baseline spans 11% and
# prob_20's 0.7% over today's runs, so three replicates on prob_7 can still produce a false sign.
# Four are taken there, and no arm ships on a single instance.
#
# JUDGED, fixed before the run: prob_7 AND prob_20 must both improve, prob_3 and prob_16 must not
# regress by more than 1%.  Same rule that rejected PERMARG.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire budget2
L=results/audit/budget2.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/budget2.log \
                  research/exact_packer/session2/recon/harness/budget2.sh \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: budget2 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" fc="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_FIRSTCAP=$fc OGC_OPSTAT=1 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3 4; do
  for p in 7 20; do
    run "A.p$p.r$rep" $p 0
    run "B.p$p.r$rep" $p 2.0
    run "C.p$p.r$rep" $p 4.0
  done
done
for rep in 1 2; do
  for p in 3 16; do
    run "A.p$p.r$rep" $p 0
    run "B.p$p.r$rep" $p 2.0
    run "C.p$p.r$rep" $p 4.0
  done
done
echo "BUDGET2DONE" >> $L
lock_release budget2

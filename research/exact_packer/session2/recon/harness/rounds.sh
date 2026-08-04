#!/bin/bash
# More attempts, shorter each: does the minimum over 8 draws beat the minimum over 4?
#
# WHAT MAKES THIS THE RIGHT LEVER.  The answer is already a min over four workers, so run-to-run
# variation is not about average quality -- it is about whether the good basin gets found at all.
# prob_20 under unchanged code: 12,746,324 / 10,628,401 / 10,531,622.  Two of three runs reach
# the same solution; one misses by 20%.  A minimum tightens with the number of draws.
#
# WHAT MAKES IT AFFORDABLE.  The budget is not binding, and that is measured rather than assumed:
# 240 s and 360 s give the SAME answer on stage-2 prob_1, doubling pref's slice changed nothing,
# and dropping operators that earn nothing does not help.  Time past convergence is spent, not
# used -- so halving it and doubling the draws should cost little and buy the tail.
#
# THE READING IS THE WORST CASE, NOT THE MEAN.  Three replicates per arm, and what matters is
# whether the BAD draw disappears.  An arm that averages the same but never produces the 20%
# outlier is strictly better here, because the grader sees one run.
#
# Instances picked for measured instability (20, 36) plus a stable control (15) and two more.
cd "$(dirname "$0")/.."
L=results/audit/rounds.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       OGC_ROUNDS=$3 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1; }
for r in 1 2 3; do
  for p in 20 36 15 13 26; do
    run "R1.$p.r$r" $p 1
    run "R2.$p.r$r" $p 2
  done
done
echo "ROUNDSDONE $(date -u +%H:%M)" >> $L

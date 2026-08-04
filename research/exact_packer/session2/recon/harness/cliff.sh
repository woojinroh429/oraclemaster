#!/bin/bash
# WHERE IS THE CLIFF, and how does it move with instance size?
#
# prob_36 at 180 s returns 94,668,900.  At 90 s and at 71 s it returns 4,023,023,433 -- Z1
# 603,423, Z3 exactly 0 -- which is _safe_sequential, the floor every worker produces before it
# tries anything.  Not a rounds bug: R=1 does it too.  The beam either finishes or returns
# nothing, so under its own minimum the whole portfolio has nothing to rank and the floor is the
# answer.  Degradation is a factor of 42, not a few percent.
#
# This matters beyond the rounds experiment.  The hidden time limits are not disclosed, and the
# report says so.  If a hidden instance is larger than the practice ones, or its limit shorter,
# that instance does not come back slightly worse -- it comes back as the floor.
#
# So: find the budget at which each size recovers.  300 blocks (36), 250 (20), 150 (24).
cd "$(dirname "$0")/.."
L=results/audit/cliff.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 "[$1]" --data data/stage2 >> $L 2>&1; }
for p in 36 20 24; do
  for b in 60 90 110 130 150 180; do run "c.$p.$b" $p $b; done
done
echo "CLIFFDONE $(date -u +%H:%M)" >> $L

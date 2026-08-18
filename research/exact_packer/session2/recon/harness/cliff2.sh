#!/bin/bash
# Does salvaging the partial beam remove the cliff?
#
# OGC_SALVAGE=0 reproduces today's shipped behaviour exactly (discard on deadline), =1 completes
# the best surviving state by rollout instead.  Same budgets as the map that found the cliff, so
# the two tables are directly comparable:
#
#     blocks          60s  90s 110s 130s     shipped
#     prob_36  300     X    X    X   ok      4,023,023,433 at 110s vs 96,871,459 at 130s
#     prob_20  250     X    X   ok   ok      1,858,390,507 at  90s vs 12,970,522 at 110s
#
# Two things have to hold.  Below the cliff the answer must stop being the floor -- that is the
# whole point.  ABOVE the cliff nothing may change: the salvage path only runs when the loop
# breaks early, so 180 s results should be untouched, and if they are not, the change is doing
# something it was not meant to.
cd "$(dirname "$0")/.."
L=results/audit/cliff2.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       OGC_SALVAGE=$4 /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 "[$1]" \
           --data data/stage2 >> $L 2>&1; }
for p in 36 20; do
  for b in 60 90 110 180; do
    run "s0.$p.$b" $p $b 0
    run "s1.$p.$b" $p $b 1
  done
done
echo "CLIFF2DONE $(date -u +%H:%M)" >> $L

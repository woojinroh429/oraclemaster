#!/bin/bash
# Three questions, in the order that can disqualify the change.
#
# 1. DOES IT OVERRUN.  The salvage rollout is not free: prob_36 at a 60 s budget went from
#    "ran 47s" to "ran 66s", a 6 s overrun of the limit itself.  The grader scores an overrun as
#    -1, so if 180 s runs come back over 180 s this is rejected whatever else it does.
# 2. DOES IT CHANGE ANYTHING ABOVE THE CLIFF.  The salvage only runs when the beam passes its
#    deadline.  Where the beam finishes, results must be identical -- if they are not, the change
#    is doing something it was not meant to.
# 3. IS THE 60 s RESULT REAL.  prob_36 at 60 s returned 82,476,859 against 94.5-96.9M over six
#    180 s runs of the shipped build.  A third of the budget beating every full run is a large
#    claim off one draw.
cd "$(dirname "$0")/.."
L=results/audit/salv180.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       timeout $(( $3 * 3 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 "[$1]" \
           --data data/stage2 >> $L 2>&1; }
for r in 1 2; do
  for p in 36 20 13 26 25; do run "n180.$p.r$r" $p 180; done   # overrun + value at the real budget
  for p in 36 20; do run "n60.$p.r$r" $p 60; done              # is the short-budget result real
done
echo "SALV180DONE $(date -u +%H:%M)" >> $L
awk '/^P/{for(i=1;i<=NF;i++) if($i=="ran"){gsub("s","",$(i+1)); b=$3; gsub("s","",b);
      if($(i+1)+0 > b+0) print "  OVERRUN " $0}}' $L

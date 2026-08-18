#!/bin/bash
# Does the shipped configuration ever run past its budget?  The grader scores an overrun as -1,
# so a slow answer and a missing answer are not on the same scale.
#
# The risk is structural and named in bayrepack: cranepack's conflict-graph build is
# uninterruptible, so a tier that is mispredicted cannot be cut short.  That is what capped NOUT
# at 40 and the grid step at 4.  The build is now parallel (19.3 s -> 13.5 s on the 43,320-column
# case), which should widen the margin rather than narrow it -- but "should" is not a measurement.
#
# Densest and largest instances first, at the real budget, shipped defaults.
cd "$(dirname "$0")/.."
L=results/audit/overrun.log; : > $L
for p in 36 13 25 30 34 40 12 16 23 26; do
  /usr/bin/python3.12 harness/run1.py myalgorithm $p 180 "ovr" --data data/stage2 >> $L 2>&1
done
echo OVRDONE >> $L
awk '/^P/{ for(i=1;i<=NF;i++) if($i=="ran") { gsub("s","",$(i+1)); if($(i+1)+0 > 180) print "  OVERRUN: " $0 } }' $L
echo "최대 실행시간: $(awk '/^P/{for(i=1;i<=NF;i++) if($i=="ran"){gsub("s","",$(i+1)); if($(i+1)+0>m) m=$(i+1)+0}} END{print m"s"}' $L) / 180s 예산"

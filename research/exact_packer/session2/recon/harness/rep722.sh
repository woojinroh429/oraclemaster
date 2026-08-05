#!/bin/bash
# The last question before this ships: are P7 (+38%) and P22 (+30%) real?
#
# They are the only losses over 10% in 37 paired instances and both are small.  Every single draw
# checked today has shrunk on replication -- prob_20's -17.37% became -0.9% over three, prob_15's
# +6.63% became +3.0% -- so a pair of unreplicated 30%+ losses is exactly what has been wrong
# before.  Three replicates per arm.
#
# COMMITS AS IT GOES.  Three untracked logs have been taken by container rewinds today, the last
# one three pairs from the end of a four-hour run.  A committed file survives the rewind, so this
# commits after every run rather than at the end.
cd "$(dirname "$0")/.."
L=results/audit/rep722.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       env $3 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1
       ( cd ../../.. && git add -A research/exact_packer/session2/recon/results/audit/rep722.log \
         && git commit -q -m "in-flight: rep722 $1" 2>/dev/null ) ; }
for r in 1 2 3; do
  for p in 7 22; do
    run "ctl.$p.r$r" $p "OGC_BEAMAIM=0.90"
    run "mix.$p.r$r" $p "OGC_NOTHING=1"
  done
done
echo "REP722DONE $(date -u +%H:%M)" >> $L

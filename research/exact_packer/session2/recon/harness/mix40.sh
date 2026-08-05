#!/bin/bash
# The aim as a PORTFOLIO AXIS, validated on all forty.
#
# Odd workers run OGC_BEAMAIM=0.10, even ones 0.90, and algorithm() returns the minimum over all
# four -- so the setting that suits the instance wins and the other is discarded, with no size
# test anywhere.  Measured at a single constant, 0.10 was -24.3% to -11.9% on 250-300 blocks and
# +25.09% on prob_1's 150, which is exactly the split a portfolio absorbs and a constant cannot.
#
# The control arm forces OGC_BEAMAIM=0.90 for every worker, which is today's shipped behaviour.
# The test arm sets nothing and lets the split happen.
#
# This is the gate for shipping: the mixed arm must not lose to the control on the small
# instances, because there its low-aim workers are pure waste of two of the four.
cd "$(dirname "$0")/.."
L=results/audit/mix40.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       env $3 timeout 600 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1; }
for p in $(seq 1 40); do
  run "ctl.$p" $p "OGC_BEAMAIM=0.90"
  run "mix.$p" $p "OGC_NOTHING=1"
done
echo "MIX40DONE $(date -u +%H:%M)" >> $L

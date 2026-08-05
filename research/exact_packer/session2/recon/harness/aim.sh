#!/bin/bash
# What should the beam aim at, now that the rest of its slice has a use?
#
# The adaptive width narrows the beam to finish inside time_budget_s*AIM.  At 0.90 the salvage
# rollout gets 10%, which a 300-block rollout does not fit in, and prob_25's 180 s runs took
# 220 s and 226 s.  A lower aim narrows the beam -- less search -- and hands the difference to
# the rollout that finishes the job.  Somewhere between is a setting that keeps the -7% to -11%
# and stops overrunning.
#
# BOTH readings matter and the runtime one can disqualify: an arm that scores well at 220 s of a
# 180 s budget is not usable.  The instances are the three that actually improved, plus prob_20
# as a control that did not (it should stay flat whatever the aim).
cd "$(dirname "$0")/.."
L=results/audit/aim.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       OGC_BEAMAIM=$3 timeout 500 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1; }
for a in 0.90 0.75 0.60 0.45; do
  for p in 25 13 36 20; do run "a$a.$p" $p $a; done
done
echo "AIMDONE $(date -u +%H:%M)" >> $L

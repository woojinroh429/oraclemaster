#!/bin/bash
# The ladder on the remaining 24 instances, plus replicates of the two outliers.
#
# Sixteen gave 9 better / 6 worse / 1 same, mean -1.23%, median -0.64%.  Dropping BOTH outliers
# (P20 -17.4%, P15 +6.6%) leaves mean and median at -0.64% together, so the middle of the
# distribution really is on the good side -- but 9-6 is p about 0.30 and decides nothing.  Forty
# paired instances is the standard per-seat pricing was held to and it is what this needs.
#
# The two outliers also get three replicates per arm.  -17.4% is far outside any spread measured
# on this machine (3-8%), and reporting a single draw as a result is the error that had to be
# retracted on prob_34.  P15 matters for a different reason: it bought 639 preference points for
# 180 days of tardiness on an instance where that is 383,400 against 1,200,060 -- the trade
# happened and was paid for three times over, which the per-bay price cannot see.
cd "$(dirname "$0")/.."
L=results/audit/latek.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       OGC_LATEK=$3 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1; }
for r in 2 3; do for p in 20 15; do run "k1.$p.r$r" $p 1; run "k3.$p.r$r" $p 3; done; done
for p in 1 2 4 5 7 8 9 11 12 13 16 17 18 21 22 23 26 27 28 30 31 33 34 39 40; do
  run "k1.$p" $p 1
  run "k3.$p" $p 3
done
echo "LATEK2DONE $(date -u +%H:%M)" >> $L

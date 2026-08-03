#!/bin/bash
# The same per-operator accounting, on the family it has never been run on.
#
# The profile that made bay look worthless -- 19.4% of the budget for a gain of 22 -- was taken
# on prob_36 / 24 / 15, and all three of those have ZERO blocks with 10 or more orientations.
# Ten of the forty final-round instances are the other family (every block at 12 orientations),
# and the preliminary set contained none of them at all.  So that profile speaks for 30 of 40
# instances and is silent about the rest.
#
# P1, P4, P27, P35: 100% / 100% / 99% / 100% high-orientation.  P35 is also 66% three-layer-plus,
# so the two axes are not confounded across the four.
cd "$(dirname "$0")/.."
L=results/audit/opstat_hi.log; : > $L
for p in 1 4 27 35; do
  echo "===== prob_$p =====" >> $L
  OGC_OPSTAT=1 WORKERS=1 /usr/bin/python3.12 harness/run1.py myalgorithm $p 180 "hi.$p" \
      --data data/stage2 >> $L 2>&1
done
echo OPSTATHIDONE >> $L

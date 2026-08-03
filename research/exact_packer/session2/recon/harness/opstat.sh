#!/bin/bash
# Which operator burns the budget, and what does it return for it?
#
# The loop has always kept tried/spent/gain per operator for its own scheduling and has never
# printed them.  "Useless but expensive" is exactly gain 0 with a large %budget, and until now
# nothing in this directory could name such an operator.
#
# One worker (WORKERS=1), because four workers racing on four cores report contention rather
# than shape.  Three instances spanning the density range of the final-round practice set.
cd "$(dirname "$0")/.."
L=results/audit/opstat.log; : > $L
for p in 36 24 15; do
  echo "===== prob_$p =====" >> $L
  OGC_OPSTAT=1 WORKERS=1 /usr/bin/python3.12 harness/run1.py myalgorithm $p 180 "ops.$p" \
      --data data/stage2 >> $L 2>&1
done
echo OPSTATDONE >> $L

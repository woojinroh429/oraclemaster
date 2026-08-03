#!/bin/bash
# Is prob_36's +0.69% a real loss, or is it inside the instance's own run-to-run spread?
#
# The late window was built to trade Z1 up for Z3 down.  On prob_36 the OPPOSITE happened:
# Z1 -31 (better) and Z3 +1014 (worse).  That is not the mechanism misfiring -- the mechanism
# cannot lower Z1 -- it is the search taking a different path because it was offered different
# candidate times.  Before tightening a formula that is already the exact breakeven bound
# (d <= w3*regret/w1), measure whether prob_36 answers the SAME question twice.
#
# Three replicates per arm, serial, same deadline.  If the latewin=0 arm alone spreads by more
# than 0.69% then the single pair proved nothing about this instance either way.
cd "$(dirname "$0")/.."
L=results/audit/lw36.log; : > $L
for r in 1 2 3; do
  for a in 0 1; do
    OGC_LATEWIN=$a timeout 400 python3 harness/run1.py myalgorithm 36 180 "lw$a.r$r" --data data/stage2 \
      | sed "s/^/latewin=$a r$r  /" >> $L 2>&1
  done
done
echo LW36DONE >> $L

#!/bin/bash
# The floor sweep's own control proved it noisy: floor=1.00 makes w(o) = 1.0 for every
# neighbour, which is arithmetically plain contact, yet it scored 0.74% off floor=0.00.  The
# beam is time-limited, so building the weight array costs nodes and the answer moves.  A
# single point per floor cannot resolve a peak against that.  Three repeats each, interleaved
# by round rather than blocked by floor, so a slow patch of machine hits every arm equally.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech)\.py' >/dev/null; }
while busy; do sleep 20; done
for r in 1 2 3; do
  for f in 0.00 0.05 0.30 0.50 0.70; do
    python3.12 harness/beam2.py myalg_base 6 150 $f "r$r" >> _n/floor6rep.log 2>&1
  done
done
echo FLOORREP-DONE >> _n/floor6rep.log

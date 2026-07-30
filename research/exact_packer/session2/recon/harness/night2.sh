#!/bin/bash
# One serialized queue.  Two overlapping queues on four cores corrupted a P5 pair earlier in
# this session, so nothing here runs concurrently with anything else.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech)\.py' >/dev/null; }
while busy; do sleep 20; done

# 1. mechanism: what does the cohort weighting actually change about the packing
python3.12 harness/mech.py 6 150 >> _n/mech6.log 2>&1

# 2. is 0.3 the right floor?  1.0 collapses to plain contact, 0.05 is nearly pure overlap.
for f in 0.00 0.05 0.15 0.30 0.50 0.70 1.00; do
  python3.12 harness/beam2.py myalg_base 6 150 $f >> _n/floor6.log 2>&1
done

# 3. does the win generalise to P5?  Same pair, P5's real limit.
for i in 1 2; do
  python3.12 harness/run1.py myalg_orig 5 600 "origv2"     >> _n/p5.log 2>&1
  python3.12 harness/run1.py myalg_base 5 600 "origv2+coh" >> _n/p5.log 2>&1
done
echo NIGHT2-DONE >> _n/p5.log

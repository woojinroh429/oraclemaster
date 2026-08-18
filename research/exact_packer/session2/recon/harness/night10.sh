#!/bin/bash
# Confirm the cohort gain at P6's real limit now that the weighting is free.
# Two interleaved pairs; the mirror pushes each line as it lands, so a reset costs at most
# the run in flight.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect)\.py' >/dev/null; }
while busy; do sleep 20; done
for r in 1 2; do
  python3.12 harness/run1.py myalg_orig 6 900 "ctl900-r$r" >> _n/coh900.log 2>&1
  python3.12 harness/run1.py myalg_base 6 900 "coh900-r$r" >> _n/coh900.log 2>&1
done
echo COH900-DONE >> _n/coh900.log

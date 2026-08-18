#!/bin/bash
# The cohort 900s pair, re-queued behind the pos_lam sweep.
cd "$(dirname "$0")/.."
while ! grep -q PLAM-DONE _n/plam.log 2>/dev/null; do sleep 30; done
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/run1.py myalg_orig 6 900 "ctl900-r2" >> _n/coh900.log 2>&1
python3.12 harness/run1.py myalg_base 6 900 "coh900-r2" >> _n/coh900.log 2>&1
echo COH900-DONE >> _n/coh900.log

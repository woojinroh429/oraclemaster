#!/bin/bash
# floor 0.5 beat floor 0.3 by a clear margin on repeated single beams (-5.06% vs -2.87% off
# the same control, and 3/3 identical), so take it to the real limits.  myalg_orig is
# deterministic on both P6 and P5 -- identical to the digit across every run so far -- so one
# control run is enough to catch machine drift; the budget goes to the arm instead.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/run1.py myalg_orig 6 900 "origv2-ctl" >> _n/c5.log 2>&1
python3.12 harness/run1.py myalg_c5   6 900 "coh0.5"     >> _n/c5.log 2>&1
python3.12 harness/run1.py myalg_c5   5 600 "coh0.5"     >> _n/c5.log 2>&1
python3.12 harness/run1.py myalg_c5   6 900 "coh0.5"     >> _n/c5.log 2>&1
python3.12 harness/run1.py myalg_c5   5 600 "coh0.5"     >> _n/c5.log 2>&1
echo C5-DONE >> _n/c5.log

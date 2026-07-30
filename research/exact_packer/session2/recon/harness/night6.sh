#!/bin/bash
# Pipeline-level screen at a third of P6's real limit.  The floor sweep taught the lesson: a
# single beam ranked floor 0.5 best by 5%, and at the real limit it LOST to the control by
# 1.6%.  Single-beam ranking does not transfer, so screen where the answer will be used --
# the whole pipeline, four workers, all stages -- just at a shorter budget.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech)\.py' >/dev/null; }
while busy; do sleep 20; done
for r in 1 2; do
  python3.12 harness/run1.py myalg_orig 6 300 "ctl"      >> _n/screen6.log 2>&1
  python3.12 harness/run1.py myalg_base 6 300 "coh0.3"   >> _n/screen6.log 2>&1
  python3.12 harness/run1.py myalg_co   6 300 "cohorder" >> _n/screen6.log 2>&1
  python3.12 harness/run1.py myalg_sh1  6 300 "shadow1"  >> _n/screen6.log 2>&1
done
echo SCREEN6-DONE >> _n/screen6.log

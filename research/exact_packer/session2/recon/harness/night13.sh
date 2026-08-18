#!/bin/bash
# A 16-second greedy construction (flatbl, step=1) scores 28,493,452 on P6 -- 5% better than
# our whole 900s pipeline and within 0.4% of the deployed build's 900s answer.  So the open
# questions are no longer about scoring terms:
#   1. is it stable, or was 28.49M a lucky single build?  Repeat it, and try the remaining modes.
#   2. does it hold at P5's regime too, where the deployed build DOES run a beam?
#   3. the second cohort pair at 900s, to finish what was queued.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while busy; do sleep 20; done
for r in 1 2; do
  for m in flatbl bigleft prefaware prefmid diagonal; do
    python3.12 harness/bigleft.py 6 120 $m 1 >> _n/modes6.log 2>&1
  done
done
for m in flatbl prefaware; do
  python3.12 harness/bigleft.py 5 120 $m 1 >> _n/modes5.log 2>&1
done
echo MODES-DONE >> _n/modes6.log
python3.12 harness/run1.py myalg_orig 6 900 "ctl900-r2" >> _n/coh900.log 2>&1
python3.12 harness/run1.py myalg_base 6 900 "coh900-r2" >> _n/coh900.log 2>&1
echo COH900-DONE >> _n/coh900.log

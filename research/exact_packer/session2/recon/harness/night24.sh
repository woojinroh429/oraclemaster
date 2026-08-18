#!/bin/bash
# GRASP broke 28M: k=6 built 27,887,068 and polished to 27,786,975, past the deployed build's
# 28,373,827 by 2.1%.  Two things the run says:
#   - wider is better.  k=3 reached only 28,194,724 where k=6 reached 27,887,068, so the top of
#     the k range has not been seen.
#   - it had not converged.  The last improvement landed at draw 34 of 43, so the budget is
#     still buying quality -- which is the property the fixed-order construction never had.
# So push both: wider draws, and more of them.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp)\.py' >/dev/null; }
while busy; do sleep 20; done
for k in 10 16 25; do
  python3.12 harness/grasp.py 6 600 300 $k flatbl 777 >> _n/grasp2.log 2>&1
done
echo GRASPK-DONE >> _n/grasp2.log
# more draws at the best k so far, and a second seed to separate the k from the luck
python3.12 harness/grasp.py 6 1500 300 6 flatbl 777  >> _n/grasp2.log 2>&1
python3.12 harness/grasp.py 6 600  300 6 flatbl 4242 >> _n/grasp2.log 2>&1
echo GRASP2-DONE >> _n/grasp2.log

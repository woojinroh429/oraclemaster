#!/bin/bash
# k=16 and k=25 are past the peak -- k=10 already improved on the pure greedy zero times in 43
# draws -- so their slots go to the memory version instead.  Keep the two plain-GRASP runs still
# worth having: k=6 with more draws, and k=6 on a second seed to tell the k from the luck.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/grasp2.py 6 600 250 flatbl 777  >> _n/g2.log 2>&1
python3.12 harness/grasp2.py 6 600 250 flatbl 4242 >> _n/g2.log 2>&1
echo G2-DONE >> _n/g2.log
python3.12 harness/grasp.py  6 1500 300 6 flatbl 777 >> _n/g2.log 2>&1
python3.12 harness/grasp2.py 5 400 200 flatbl 777    >> _n/g2.log 2>&1
echo G2B-DONE >> _n/g2.log

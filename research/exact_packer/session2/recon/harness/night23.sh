#!/bin/bash
# GRASP over the construction, which is where P6 is decided and where the budget is currently
# idle: 15s to build, 300s to polish (and the polish provably converges -- 300s and 800s land
# 28,138,113 to the digit), leaving ~585s of a 900s limit doing nothing on the instance whose
# construction settles 97% of the objective.
#
# k=1 reproduces sac3 exactly, so k>1 is a strict relaxation of the best key we have rather than
# a different idea.  Two k values and two seeds to see whether the draws find anything the six
# named orders do not, then the same run on P5.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/grasp.py 6 600 300 3 flatbl 12345 >> _n/grasp.log 2>&1
python3.12 harness/grasp.py 6 600 300 6 flatbl 777   >> _n/grasp.log 2>&1
python3.12 harness/grasp.py 6 600 300 3 diagonal 999 >> _n/grasp.log 2>&1
echo GRASP-DONE >> _n/grasp.log
python3.12 harness/grasp.py 5 400 200 3 flatbl 12345 >> _n/grasp.log 2>&1
echo GRASP5-DONE >> _n/grasp.log

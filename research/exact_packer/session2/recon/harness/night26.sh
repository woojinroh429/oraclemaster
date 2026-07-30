#!/bin/bash
# GRASP2 with the reactive rule corrected: reward a k for setting a new incumbent, not for
# beating the running median.  The first version's weights told the story -- 3:2.25 4:2.60
# 6:1.04 8:1.27 -- it converged onto the narrow values and starved k=6, which had won the fixed
# sweep, and finished at 28,129,619 against plain GRASP k=6's 27,786,975.
#
# Two seeds against the plain k=6 baseline, then P5 to see whether the adaptive k picks a
# different value in a regime where the construction loses on its own.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/grasp2.py 6 600 250 flatbl 777  >> _n/g3.log 2>&1
python3.12 harness/grasp2.py 6 600 250 flatbl 4242 >> _n/g3.log 2>&1
echo G3-DONE >> _n/g3.log
python3.12 harness/grasp2.py 6 1200 250 flatbl 31337 >> _n/g3.log 2>&1
python3.12 harness/grasp2.py 5 400 200 flatbl 777     >> _n/g3.log 2>&1
echo G3B-DONE >> _n/g3.log

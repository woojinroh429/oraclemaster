#!/bin/bash
# Give P5 a fair GRASP.  The earlier P5 run anchored on flatbl/sac3 -- P6's winner -- which
# starts P5 at 12,121,880 where its own best construction, bigleft/rank, starts at 10,216,744.
# GRASP still pulled that bad anchor down 12.3%, to 10,631,125, so the run said nothing about
# whether GRASP suits P5; it only said the anchor was wrong.  If the same 12% comes off
# bigleft/rank the result lands near 8.96M, against the beam's 9,044,458 and the deployed
# build's 8,972,672 -- so this is worth settling rather than assuming.
#
# P3 and P4 too, for the same reason: nobody has actually looked.  P3 has Z1 = 0, so a method
# whose whole premise is "the construction decides the tardiness" should have nothing to offer
# there -- which is a prediction worth testing rather than asserting.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/grasp.py 5 400 100 6 bigleft rank 777  >> _n/fair.log 2>&1
python3.12 harness/grasp.py 5 400 100 6 flatbl  rank 777  >> _n/fair.log 2>&1
python3.12 harness/grasp.py 5 400 100 6 bigleft rank 4242 >> _n/fair.log 2>&1
echo FAIR5-DONE >> _n/fair.log
python3.12 harness/grasp.py 4 300 100 6 bigleft rank 777  >> _n/fair.log 2>&1
python3.12 harness/grasp.py 3 150 60  6 bigleft rank 777  >> _n/fair.log 2>&1
echo FAIR-DONE >> _n/fair.log

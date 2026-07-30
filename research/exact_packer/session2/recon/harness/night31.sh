#!/bin/bash
# grasp.py takes PROB BUDGET POL K MODE SEED BASE.  night29 passed MODE BASE SEED and every run
# died on int('rank') before doing any work.
#
# Give P5 the fair test its earlier run never got: anchored on bigleft/rank, which starts P5 at
# 10,216,744 where flatbl/sac3 -- P6's winner, and what the first attempt used -- starts it at
# 12,121,880.  GRASP pulled 12.3% off that bad anchor, and the same proportion off the good one
# lands near 8.96M, against the beam's 9,044,458 and the deployed build's 8,972,672.
#
# P4 and P3 for the same reason: nobody has looked.  P3 should be the interesting negative --
# its Z1 is 0, so a method whose premise is that the construction settles the tardiness has
# nothing to settle there.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2|base345)\.py' >/dev/null; }
# Wait on night30's sentinel, not just the process table -- two queues polling the same busy()
# can see an idle machine on the same tick and start together.
while ! grep -q HEADROOM-DONE _n/base345.log 2>/dev/null; do sleep 30; done
while busy; do sleep 20; done
python3.12 harness/grasp.py 5 400 100 6 bigleft 777  rank >> _n/fair2.log 2>&1
python3.12 harness/grasp.py 5 400 100 6 bigleft 4242 rank >> _n/fair2.log 2>&1
python3.12 harness/grasp.py 4 300 100 6 bigleft 777  rank >> _n/fair2.log 2>&1
python3.12 harness/grasp.py 3 150 60  6 bigleft 777  rank >> _n/fair2.log 2>&1
echo FAIR2-DONE >> _n/fair2.log

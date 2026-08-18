#!/bin/bash
# construction + our polish lands 28,138,113 on P6 in 420 of the 900 seconds available, past
# the deployed build's 28,373,827.  The polish used its whole 300s, so it may not be finished;
# and the construction is 120s of which it needs 15.  Spend the real budget: 60s to build,
# 800s to polish.  Also whether the pairing prefers a different construction -- diagonal has
# the same Z1 without the small-block rule, so it may leave more for the polish to take.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|sepcheck)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/polish.py 6 60 800 flatbl   sac3 0.60 >> _n/polish.log 2>&1
python3.12 harness/polish.py 6 60 800 diagonal sac3 0.60 >> _n/polish.log 2>&1
python3.12 harness/polish.py 6 60 800 flatbl   sac4 0.60 >> _n/polish.log 2>&1
python3.12 harness/polish.py 5 60 500 flatbl   sac3 0.60 >> _n/polish.log 2>&1
echo POLISH-DONE >> _n/polish.log

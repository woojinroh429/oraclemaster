#!/bin/bash
# The polish converges: 300s and 800s both land 28,138,113 exactly, so more budget on the
# operator buys nothing and that number is the ceiling for this construction paired with it.
# What is left is the pairing.  diagonal builds worse (28,436,084) but leaves Z3 at 10302
# against flatbl's 9506, so there is more for the polish to take -- the question is whether it
# takes enough to overtake.  Its run was cut off by a container reset; re-queue it, plus sac4,
# plus P5 where the construction loses badly on its own.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|sepcheck)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/polish.py 6 60 400 diagonal sac3 0.60 >> _n/polish2.log 2>&1
python3.12 harness/polish.py 6 60 400 flatbl   sac4 0.60 >> _n/polish2.log 2>&1
python3.12 harness/polish.py 6 60 400 flatbl   sac3 0.75 >> _n/polish2.log 2>&1
python3.12 harness/polish.py 6 60 400 prefmid  sac3 0.60 >> _n/polish2.log 2>&1
python3.12 harness/polish.py 5 60 400 flatbl   sac3 0.60 >> _n/polish2.log 2>&1
echo POLISH2-DONE >> _n/polish2.log

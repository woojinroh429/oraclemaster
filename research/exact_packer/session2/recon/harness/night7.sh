#!/bin/bash
# The deployed build scores 28.37M on P6 where the rebuild scores 30.3M -- 6.4% already in
# hand, in code that is already in this repo.  Every scoring term invented tonight has been
# worth a fraction of that.  So stop inventing and measure what the deployed build does
# differently, in the terms the mechanism probe established: window alignment, free-region
# granularity, the swept factor, the shadow factor, entry delay.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/run1.py myalgorithm 6 900 "DEPLOYED" >> _n/deployed.log 2>&1
python3.12 harness/dissect.py 6 300 myalg_orig,myalgorithm >> _n/dissect6.log 2>&1
python3.12 harness/run1.py myalgorithm 5 600 "DEPLOYED" >> _n/deployed.log 2>&1
echo NIGHT7-DONE >> _n/deployed.log

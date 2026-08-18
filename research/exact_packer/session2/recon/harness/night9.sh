#!/bin/bash
# Re-run what the scoring bug threw away.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/run1.py myalgorithm 6 900 "DEPLOYED" >> _n/deployed.log 2>&1
python3.12 harness/run1.py myalgorithm 5 600 "DEPLOYED" >> _n/deployed.log 2>&1
echo NIGHT9-DONE >> _n/deployed.log

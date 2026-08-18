#!/bin/bash
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/mech.py 6 150 >> _n/mech6fix.log 2>&1
python3.12 harness/mech.py 5 150 >> _n/mech5fix.log 2>&1
echo NIGHT3-DONE >> _n/mech5fix.log

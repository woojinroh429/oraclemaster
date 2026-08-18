#!/bin/bash
# Is P3's 97,570 a local optimum, or a basin?  Both terms are closed locally -- Z3's 24 misplaced
# blocks are blocked at every tardiness-free time, and Z2 can only be fixed by paying preference
# at 30:1 -- yet competitors report 70,000-84,000.  Perturb the bay assignment and let the beam
# re-pack around it, which is the one thing the local analysis cannot rule out.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2|bgrasp|base345|shake|whyz)\.py' >/dev/null; }
while busy; do sleep 20; done
for k in random balance pref; do
  python3.12 harness/shake.py 3 420 $k 0.15 myalg_base 777 >> _n/shake.log 2>&1
done
echo SHAKE3-DONE >> _n/shake.log
python3.12 harness/shake.py 3 420 random 0.35 myalg_base 4242 >> _n/shake.log 2>&1
python3.12 harness/shake.py 4 420 random 0.15 myalg_base 777  >> _n/shake.log 2>&1
echo SHAKE-DONE >> _n/shake.log

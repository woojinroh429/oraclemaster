#!/bin/bash
# Re-run the shake with the instrument fixed.  The first pass logged only improvements, so
# "random and balance both gained nothing in four rounds" could equally mean the basin is deep
# or the perturbation never reached the solution -- and those call for opposite next steps.
# Now every round prints its objective and how many blocks the regrow actually left in a
# different bay than the incumbent, which answers it directly.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2|bgrasp|base345|shake|whyz)\.py' >/dev/null; }
while busy; do sleep 20; done
for k in random balance pref; do
  python3.12 harness/shake.py 3 300 $k 0.30 myalg_base 4242 >> _n/shake2.log 2>&1
done
echo SHAKE2-DONE >> _n/shake2.log

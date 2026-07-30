#!/bin/bash
# Make flatness primary and see what happens.  The deployed build's construction ranks
# candidates by h first and beats our whole 900s pipeline in sixteen seconds; our score has
# the same h term but an order of magnitude under contact.  pos_lam is that weight.  contact
# peaks near 44 on these blocks and h spans [0,15], so pos_lam has to reach a few units before
# flatness leads -- 10x, 40x and 100x on the axes' 0.05-0.20 brackets that range.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while busy; do sleep 20; done
for r in 1 2; do
  python3.12 harness/run1.py myalg_base  6 300 "pl1-r$r"   >> _n/plam.log 2>&1
  python3.12 harness/run1.py myalg_pl10  6 300 "pl10-r$r"  >> _n/plam.log 2>&1
  python3.12 harness/run1.py myalg_pl40  6 300 "pl40-r$r"  >> _n/plam.log 2>&1
  python3.12 harness/run1.py myalg_pl100 6 300 "pl100-r$r" >> _n/plam.log 2>&1
done
echo PLAM-DONE >> _n/plam.log

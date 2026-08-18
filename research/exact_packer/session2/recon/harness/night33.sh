#!/bin/bash
# P3: the beam never looks at preference at all.
#
# sc = -contact + position + prefw*pen, and every axis carries prefw=0.0, so the penalty term is
# dead and bay preference enters the placement decision nowhere -- it is only touched afterwards
# by the z3_improve polish.  That is defensible on a saturated instance.  P3 has a demand ratio
# of 0.327: the yard fills a third of the way, everything fits, and there is nothing to pack
# around.  So on P3 the beam optimises a congestion problem that does not exist and pays for it
# in preference, which is 78% of P3's objective (Z3 546 at w3 150 against Z2 3134 at w2 5, and
# Z1 is 0).
#
# Competitors well below us overall are scoring 70,000-84,000 on P3 where we score 97,570, which
# is the shape of a structural miss rather than a tuning gap.  Z3's floor is 134 against our 546,
# so 62,550 is recoverable there and the target only needs 17,570 of it.
#
# Sweep prefw over the axes.  mu (the contact scale) is 1e-3*min(w1,w3)*mum, so on P3 contact is
# worth ~0.02 per cell against a preference gap that runs to tens -- meaning even a small prefw
# should dominate, and the interesting range is low.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2|bgrasp|base345)\.py' >/dev/null; }
while busy; do sleep 20; done
for w in 0.5 2 8 32; do
  OGC_PREFW=$w python3.12 harness/base345.py 3 myalg_pw >> _n/prefw.log 2>&1
done
echo PREFW3-DONE >> _n/prefw.log
# P4 is 20% Z3 at demand ratio 0.702 -- less slack, so the same lever should be weaker but not
# necessarily absent.
for w in 0.5 2 8; do
  OGC_PREFW=$w python3.12 harness/base345.py 4 myalg_pw >> _n/prefw.log 2>&1
done
echo PREFW4-DONE >> _n/prefw.log

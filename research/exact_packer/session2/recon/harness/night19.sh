#!/bin/bash
# Patching the beam's score to imitate the construction has now failed three times -- pos_lam,
# span as a penalty in the sum, and the lexicographic key with h corrected and the small-block
# branch in place.  The corrected key still lands Z1 5411-6185 against the construction's 4052,
# a gap far too large to be about where a block sits; it is about when blocks enter.  So stop
# rebuilding the construction and tune the one that already works, on the two knobs its own
# ablation points at and nobody has set for P6.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while busy; do sleep 20; done
for th in 0.30 0.45 0.75 0.90 1.00; do
  python3.12 harness/bigleft.py 6 120 flatbl 1 rank $th >> _n/ctune.log 2>&1
done
for od in tri2 stdens stdens_u sac3 prio; do
  python3.12 harness/bigleft.py 6 120 flatbl 1 $od 0.60 >> _n/ctune.log 2>&1
done
echo CTUNE-DONE >> _n/ctune.log

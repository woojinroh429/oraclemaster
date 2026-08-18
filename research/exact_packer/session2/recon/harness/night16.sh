#!/bin/bash
# pos_lam refuted the "just weight h higher" reading: x40 cost 6.4% and x100 7.6%, with Z1
# worsening alongside, so it is not a trade -- it is loss.  A weighted sum cannot express what
# the construction key does.  Raising pos_lam does not promote h to first place, it deletes
# contact: blocks stop touching, spread out, and the free space fragments, which is why Z1 goes
# with it.  The construction sorts by h and then orders the TIES by (wy, wx), keeping the free
# region contiguous -- a structure a sum has no way to represent.
#
# Which is the argument for the floor-span term instead: it charges fragmentation directly,
# as its own term, without dismantling contact.  Sweep it where pos_lam was swept.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while busy; do sleep 20; done
for r in 1 2; do
  python3.12 harness/run1.py myalg_base 6 300 "sp0-r$r"  >> _n/span.log 2>&1
  python3.12 harness/run1.py myalg_sp1  6 300 "sp1-r$r"  >> _n/span.log 2>&1
  python3.12 harness/run1.py myalg_sp4  6 300 "sp4-r$r"  >> _n/span.log 2>&1
  python3.12 harness/run1.py myalg_sp16 6 300 "sp16-r$r" >> _n/span.log 2>&1
done
echo SPAN-DONE >> _n/span.log

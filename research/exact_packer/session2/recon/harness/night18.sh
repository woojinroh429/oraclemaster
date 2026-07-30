#!/bin/bash
# Re-run the span sweep against a build where span actually reaches the scorer.  The previous
# one ran the control eight times: the axis dict carried span=4.0 and _contact_beam kept its
# 0.0 default, because the knob was threaded by a chained replace against a string an earlier
# replace had already rewritten.  Every knob is asserted now.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while busy; do sleep 20; done
for r in 1 2; do
  python3.12 harness/run1.py myalg_base 6 300 "sp0-r$r"  >> _n/span2.log 2>&1
  python3.12 harness/run1.py myalg_sp4  6 300 "sp4-r$r"  >> _n/span2.log 2>&1
  python3.12 harness/run1.py myalg_sp16 6 300 "sp16-r$r" >> _n/span2.log 2>&1
done
echo SPAN2-DONE >> _n/span2.log
# the construction knobs its own ablation points at, still unmeasured
for th in 0.30 0.45 0.75 0.90; do
  python3.12 harness/bigleft.py 6 120 flatbl 1 rank $th >> _n/ctune.log 2>&1
done
for od in tri2 stdens stdens_u; do
  python3.12 harness/bigleft.py 6 120 flatbl 1 $od 0.60 >> _n/ctune.log 2>&1
done
echo CTUNE-DONE >> _n/ctune.log

#!/bin/bash
# Where a better construction is likely to be, from the deployed build's own ablation:
#   sx (small blocks take the free-span rule)  bigleft 29.06M vs leftbottom 30.27M   -4.2%
#   tie (sweep direction)                      flatbl  28.49M vs bigleft    29.06M   -2.0%
#   preference in the key                      prefaware 30.48M                      worst
# The small-block rule is the biggest single lever in that table, and small_thresh -- the knob
# deciding who gets it -- has never been tuned for P6.  Nor has the dispatch order: the build's
# own note says "recon had only rank" while it carries five.
#
# Each build is ~23s, so the whole sweep costs less than two pipeline runs.  Best construction
# so far: flatbl/rank/0.60 at 28,493,452.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while ! grep -q SPAN-DONE _n/span.log 2>/dev/null; do sleep 30; done
while busy; do sleep 20; done
for th in 0.30 0.45 0.60 0.75 0.90; do
  python3.12 harness/bigleft.py 6 120 flatbl 1 rank $th >> _n/ctune.log 2>&1
done
for od in rank tri2 stdens stdens_u sac3 prio; do
  python3.12 harness/bigleft.py 6 120 flatbl 1 $od 0.60 >> _n/ctune.log 2>&1
done
echo CTUNE-DONE >> _n/ctune.log

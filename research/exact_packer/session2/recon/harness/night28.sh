#!/bin/bash
# Where should the 900 seconds go, draws or polish?
#
# The polish is nearly done early.  On the same build: 15s recovers 98,848 of the 123,021 it
# will ever recover, 300s recovers all of it, and 800s recovers not a unit more.  So the last
# 285 seconds of polish are worth 24,173.
#
# A draw costs 14 seconds, and when one sets a new incumbent it has moved the objective by far
# more than that: draw 1 to draw 34 was 28,261,134 -> 27,887,068, or 374,066.  285 seconds is
# twenty draws.
#
# Paired at the same 900s total, and both arms now re-rank their finalists after a short polish
# -- which matters more, not less, when the final polish is short, because the gap between
# builds survives instead of being polished away.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2)\.py' >/dev/null; }
while busy; do sleep 20; done
for s in 777 4242; do
  python3.12 harness/grasp.py 6 600 300 6 flatbl $s >> _n/split.log 2>&1
  python3.12 harness/grasp.py 6 840 60  6 flatbl $s >> _n/split.log 2>&1
done
echo SPLIT-DONE >> _n/split.log

#!/bin/bash
# The deployed build's ultra-dense answer, standalone, at P6's real limit -- and the same
# construction on P5, which is NOT in the ultra band, to see whether the win is the
# construction or the regime.  The other three modes at 300s say whether bigleft specifically
# matters or any completed full-resolution construction would do.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while busy; do sleep 20; done
python3.12 harness/bigleft.py 6 900 bigleft 1    >> _n/bigleft.log 2>&1
python3.12 harness/bigleft.py 5 600 bigleft 1    >> _n/bigleft.log 2>&1
for m in flatbl leftbottom coreperi; do
  python3.12 harness/bigleft.py 6 300 $m 1       >> _n/bigleft.log 2>&1
done
echo BIGLEFT-DONE >> _n/bigleft.log

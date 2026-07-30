#!/bin/bash
# order=sac3 builds 28,261,134 on P6 in fifteen seconds -- past the deployed build's own 900s
# answer of 28,373,827.  sac prepends a victim set to the rank order (key = (b in victims,
# rd+ra, due)), so it is a SCHEDULING change, which is exactly where the evidence said the gap
# was: three attempts to close it by changing placement score all failed, and this closes it by
# changing who goes first.
#
# So sweep the two dimensions that just moved, and their product: the victim count K, and the
# small-block threshold.  Everything here is a 15-23s build.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while busy; do sleep 20; done
for k in sac1 sac2 sac4 sac5 sac6 sac8; do
  python3.12 harness/bigleft.py 6 120 flatbl 1 $k 0.60 >> _n/sac.log 2>&1
done
for th in 0.45 0.50 0.55 0.65 0.70 0.75; do
  python3.12 harness/bigleft.py 6 120 flatbl 1 sac3 $th >> _n/sac.log 2>&1
done
for m in diagonal bigleft prefmid; do
  python3.12 harness/bigleft.py 6 120 $m 1 sac3 0.60 >> _n/sac.log 2>&1
done
echo SAC-DONE >> _n/sac.log
# does it hold at P5's regime, and at P6's real limit
python3.12 harness/bigleft.py 5 600 flatbl 1 sac3 0.60 >> _n/sac.log 2>&1
python3.12 harness/bigleft.py 6 900 flatbl 1 sac3 0.60 >> _n/sac.log 2>&1
echo SAC2-DONE >> _n/sac.log

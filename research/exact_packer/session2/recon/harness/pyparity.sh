#!/bin/bash
# Does the newly built 3.11 engine answer the same as the 3.12 one it was compiled from?
#
# It has to be asked on an IDLE box.  The first attempt gave 3.12 87.6M against 3.11 100.2M and
# the two runs did not have the same machine to themselves: watcher shells left over from an
# earlier step were spinning `while pgrep ...; do :; done` at 100% CPU, one during the 3.12 run
# and up to three during the 3.11 run, on four cores.  Everything here is wall-clock budgeted,
# so that alone can account for the gap.  Serial, nothing else running, same instance, same
# deadline, alternating so a slow patch of machine hits both.
cd "$(dirname "$0")/.."
L=results/audit/pyparity.log; : > $L
for r in 1 2; do
  OGC_LATEWIN=0 /usr/bin/python3.12 harness/run1.py myalgorithm 36 180 "p312.r$r" --data data/stage2 >> $L 2>&1
  OGC_LATEWIN=0 /usr/bin/python3.11 harness/run1.py myalgorithm 36 180 "p311.r$r" --data data/stage2 >> $L 2>&1
done
echo PARITYDONE >> $L

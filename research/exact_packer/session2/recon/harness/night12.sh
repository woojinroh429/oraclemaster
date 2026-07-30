#!/bin/bash
# The 900s confirmation, re-queued behind the bigleft measurement.  Cohort is already
# established at 300s (3/3, mean -3.30%); what bigleft scores standalone on P6 is the open
# question worth the cores first.
cd "$(dirname "$0")/.."
# Two queues polling the same busy() can both see an idle machine on the same tick and start
# together -- that is how a P5 pair got corrupted earlier tonight.  Wait on night11's sentinel,
# not just on the process table.
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft)\.py' >/dev/null; }
while ! grep -q BIGLEFT-DONE _n/bigleft.log 2>/dev/null; do sleep 30; done
while busy; do sleep 20; done
for r in 1 2; do
  python3.12 harness/run1.py myalg_orig 6 900 "ctl900-r$r" >> _n/coh900.log 2>&1
  python3.12 harness/run1.py myalg_base 6 900 "coh900-r$r" >> _n/coh900.log 2>&1
done
echo COH900-DONE >> _n/coh900.log

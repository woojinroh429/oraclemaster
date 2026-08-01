#!/bin/bash
# Validate the repack's cost model before the operator is trusted with a real budget.
#
# cranepack's time_budget_s is not a hard limit: the same call at grid step 4 returned inside
# its 120s ask, and at step 2 -- four times the position grid -- ran 18 minutes against the same
# 120s.  bayrepack now sizes the PROBLEM to the slice instead of trusting the deadline, and
# brkcost.py measures whether that rule actually holds at every slice the allocator can hand it.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1
[ -s results/brkcost.log ] || timeout 1800 python3.12 harness/brkcost.py 3 240 myalg_base > results/brkcost.log 2>&1
cat results/brkcost.log
( cd ../../.. && git add -f research/exact_packer/session2/recon/results/brkcost.log >/dev/null 2>&1 \
  && git commit -q -m "result: repack cost model -- asked vs actual at every allocator slice" >/dev/null 2>&1 )
echo "queue13done  $(date -u +%H:%M:%S)"

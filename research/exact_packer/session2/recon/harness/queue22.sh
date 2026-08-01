#!/bin/bash
# The ceiling of free repacking on P3, taken to exhaustion.
#
# Everything else now depends on this number.  p3bay0.py freed ONE bay ONCE and went 96,990 ->
# 82,175.  brk does that repeatedly inside a run and averages 87,703 against a control's 103,463
# -- but it competes for slices, sizes problems to fit them, and stops when the budget ends, and
# none of those are properties of the IDEA.
#
# So run the idea to exhaustion with no overall clock: sweep every bay, repack it freely, keep
# what the grader scores better, repeat until a full pass over all bays improves nothing.
#
#     ceiling near 70,000   the idea is enough; the rest is engineering -- make brk reach in
#                           budget what a patient loop reaches.  Scheduling and sizing, not search.
#     ceiling near 85,000   brk is already near this idea's limit, more of it will not pay, and
#                           70,000 needs a different mechanism.
#
# Runs after queue21, which is measuring the tier rule against the one it replaced.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1
[ -s results/p3ceil.log ] || timeout 5400 python3.12 harness/p3ceil.py 3 240 120 myalg_base > results/p3ceil.log 2>&1
tail -30 results/p3ceil.log
( cd ../../.. && git add -f research/exact_packer/session2/recon/results/p3ceil.log >/dev/null 2>&1 \
  && git commit -q -m "result: ceiling of free repacking on P3" >/dev/null 2>&1 )
echo "queue22done  $(date -u +%H:%M:%S)"

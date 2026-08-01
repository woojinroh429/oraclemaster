#!/bin/bash
# The ceiling measurement, redone from a GOOD starting solution.
#
# WHY IT HAS TO BE REDONE.  p3ceil started from myalg_base at 101,935 and swept every bay to
# exhaustion, reaching 92,740.  I read that as "brk is already near the ceiling of free
# repacking" -- and that was wrong, because the pipeline WITH brk reaches 82,180, well past the
# supposed ceiling.  A sweep that starts 20,000 worse and ends 10,000 worse has not measured a
# ceiling; it has measured what one sweep does from one starting point.  Comparing it to the
# pipeline's number was comparing two things with different starts, which is the error this
# session has been avoiding everywhere else.
#
# So run it from where we actually are.  myalg_brk is the arm that produced 82,180 / 86,550 /
# 86,550 / 88,720 / 90,545 / 91,670, and the sweep gets no clock.
#
#     lands near 73,000   there IS a path.  brk simply cannot reach it inside 240 s, which is a
#                         scheduling problem and not a search one.
#     lands near 80,000   free repacking tops out around there and 70,000 needs a different
#                         mechanism.
#
# Either answer is worth having, and neither is available from the run that started at 101,935.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
[ -s results/p3ceil_good.log ] || timeout 7200 python3.12 -u harness/p3ceil.py 3 240 120 myalg_brk \
    > results/p3ceil_good.log 2>&1
tail -30 results/p3ceil_good.log
( cd ../../.. && git add -f research/exact_packer/session2/recon/results/p3ceil_good.log >/dev/null 2>&1 \
  && git commit -q -m "result: repacking ceiling from a good start" >/dev/null 2>&1 )
echo "queue25done  $(date -u +%H:%M:%S)"

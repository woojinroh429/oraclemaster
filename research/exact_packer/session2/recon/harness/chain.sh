#!/bin/bash
# RUN THE WHOLE PLAN, ONE STAGE AT A TIME, AND SURVIVE A RESTART DOING IT.
#
# Four queues have to run in order and must not run together: two solvers at once change the
# wall-clock path, and a proved-exact 1.85x speedup once moved an objective by 7.7% on an
# otherwise bit-identical build.  Anything measured beside another measurement is measuring the
# other one.
#
# Sequencing them by hand means every container restart loses whatever was next.  keepalive.sh
# relaunches the queue named in harness/CURRENT, so naming THIS script there makes the plan --
# not one stage of it -- the thing that gets resumed.  Every stage skips work whose result is
# already in its log, so a relaunch re-enters where it stopped and repeats nothing.
#
#   mbay3    finish the eight-instance one-bay vs two-bay A/B
#   mbay3b   redo P9 and P26, which the 02:18 keepalive incident cost
#   mbaydbg  why the two-bay arm returns 0 application(s): declined on budget, or ran and
#            found nothing.  Those are opposite conclusions and mbay3 cannot tell them apart.
#   wspread  where the bad draw is, and whether more draws can remove it
#
# The order is deliberate.  mbaydbg only makes sense once the table it explains is complete, and
# wspread is last because it is the longest and the least dependent on the others -- if the
# container takes the machine away mid-plan, the part already finished is the part that answers
# a question something else is waiting on.
#
# CURRENT HAS TO SAY `chain` WHILE A STAGE IS RUNNING, not the stage's own name.  Every stage
# claims CURRENT as its first action -- that is what stopped a finished queue being resurrected
# after the 01:26 restart, so it stays.  But if a restart lands mid-stage and CURRENT names the
# STAGE, keepalive brings back that one stage and the rest of the plan is gone.  So each stage is
# started in the background, given a moment to write its claim, and then overwritten: the last
# writer wins and the plan is what resumes.
set -u
cd "$(dirname "$0")" || exit 1
echo chain > CURRENT
for s in mbay3 mbay3b mbaydbg wspread; do
    echo "== chain: $s $(date -u +%H:%M:%S) =="
    bash "$s.sh" &
    _p=$!
    sleep 3
    echo chain > CURRENT
    wait $_p || echo "chain: $s exited $?"
done
echo "CHAINDONE $(date -u +%H:%M:%S)"
echo idle > CURRENT

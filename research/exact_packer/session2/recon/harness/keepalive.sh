#!/bin/bash
# RELAUNCH THE EXPERIMENT QUEUE IF IT IS NOT RUNNING.  Safe to call any number of times.
#
# The container has restarted four times.  The third killed the overnight queue at 18:39 and
# nothing brought it back, so six hours produced nothing.  Results already push as they land and
# every stage skips a run whose file exists, so resuming was always free -- what was missing was
# anything to DO the resuming.
#
# An in-container watchdog cannot help, because a restart kills it too.  What does run after a
# restart is the session hook (.claude/settings.json -> SessionStart), and a COMMITTED hook
# survives the snapshot rewind that takes untracked files with it.  That is why this file is
# committed before it is used.
#
# WHY THE FIRST THING IT DOES IS CHECK THE EXPERIMENT LOCK.  SessionStart fires on COMPACTION,
# not only on a container restart, and the earlier version of this file ran
#
#     git fetch origin <branch> && git reset --hard FETCH_HEAD
#
# unconditionally.  At 04:40:40 it fired mid-compaction while askfix was running, and the reset
# rewound every TRACKED file to the remote -- including results/af_p6.log, which the live P6 run
# had just finished writing.  A fifteen-minute measurement was overwritten by its own committed
# partial, and results/askfix.log was rewound to a previous run's copy, which is why the queue
# log then disagreed with the processes actually on the machine.
#
# The rewind is only needed after a real container restart, and a real restart kills the queue.
# So: if the experiment lock is held, something is running, there was no rewind, and there is
# nothing to do.  Never touch the working tree while a measurement is in flight.
set -u
cd "$(dirname "$0")/.." 2>/dev/null || exit 0

# flock -n on the shared experiment lock: if we CANNOT take it, a queue is live -- leave.
exec 7>/tmp/ogc_experiment.lock 2>/dev/null || exit 0
flock -n 7 || exit 0
exec 7>&-

for q in overnight askfix; do
    pgrep -f "harness/${q}\.sh" >/dev/null 2>&1 && exit 0
done

# only now, with nothing running, is a rewind safe: local git can be at a pre-restart snapshot
( cd ../../.. && git fetch -q origin claude/repair-plan-model-1ig6it 2>/dev/null \
  && git reset -q --hard FETCH_HEAD 2>/dev/null )
# WHICH queue to bring back.  harness/CURRENT names it, is committed, and is updated whenever a
# new queue is launched -- so a restart resumes the work that was actually in flight instead of
# whatever overnight.sh happened to be.  Every queue skips a stage whose result file exists, so
# resuming costs nothing and repeats nothing.
Q="$(cat harness/CURRENT 2>/dev/null || echo overnight)"
[ -f "harness/$Q.sh" ] || Q=overnight
[ -f "harness/$Q.sh" ] || exit 0
mkdir -p results
nohup bash "harness/$Q.sh" >> "results/$Q.log" 2>&1 < /dev/null &
echo "queue relaunched: $Q $(date -u +%H:%M:%S)"

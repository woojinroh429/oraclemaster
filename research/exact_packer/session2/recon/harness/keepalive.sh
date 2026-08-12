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

# LIVENESS IS A WORKER, NOT A SCRIPT NAME.  pgrep -f "harness/x.sh" also matches the shell that
# is running the CHECK, so it can report a queue alive that died hours ago -- that is exactly what
# happened at 08:14, and five hours of machine time went to nothing while the check kept saying
# the queue was up.  A real run has a python worker; look for that.
#
# ANY harness worker, not run1.py alone.  The narrow pattern matched the end-to-end queues and
# nothing else, so when a compaction fired at 02:18 while mbay3 was mid-P26 -- mbay3 drives
# harness/mbay.py, never run1.py -- the check reported an idle machine and started a SECOND copy
# of the queue.  Both then appended to the same log.  The pattern has to cover every worker a
# queue can spawn, so it keys on the interpreter and the harness directory instead of one script.
pgrep -f "python3\.12 harness/" >/dev/null 2>&1 && exit 0

# only now, with nothing running, is a rewind safe: local git can be at a pre-restart snapshot
( cd ../../.. && git fetch -q origin claude/repair-plan-model-1ig6it 2>/dev/null \
  && git reset -q --hard FETCH_HEAD 2>/dev/null )
# WHICH queue to bring back.  harness/CURRENT names it, is committed, and is updated whenever a
# new queue is launched -- so a restart resumes the work that was actually in flight instead of
# whatever overnight.sh happened to be.  Every queue skips a stage whose result file exists, so
# resuming costs nothing and repeats nothing.
# THE RESTART CAN TAKE THE PYTHON ENVIRONMENT WITH IT.
#
# One restart came back with python3.12's site-packages emptied -- shapely, numpy and ortools gone
# -- while python3.11 kept its copies and `pip` still pointed at 3.11.  This script relaunched the
# queue anyway and 64 cells died on ModuleNotFoundError, recorded as crashes, which the resume
# logic then treats as finished.  Three hours of machine time produced nothing and would not have
# retried itself.
#
# Cheap to check and cheap to fix, so do both before starting anything.
if ! /usr/bin/python3.12 -c "import shapely, numpy" >/dev/null 2>&1; then
  echo "keepalive: python3.12 lost its packages after the restart; reinstalling"
  /usr/bin/python3.12 -m pip install --quiet --break-system-packages shapely numpy ortools \
      >/dev/null 2>&1 || true
  /usr/bin/python3.12 -c "import shapely, numpy" >/dev/null 2>&1 || {
      echo "keepalive: reinstall failed; refusing to start a queue that would only record crashes"
      exit 0; }
fi
# CURRENT NOW CARRIES "<tag> <pid>", NOT A BARE TAG, AND THIS READ TOOK THE WHOLE LINE.
#
# harness/lock.sh writes the owner's pid alongside the tag so a stale lock can be told from a live
# one -- that is the whole point of the owner check.  This line then asked for
# `harness/gridstep 2232.sh`, found nothing, and fell through to `overnight`.  overnight.sh is a
# finished queue whose every stage skips on an existing result file, so each restart "relaunched"
# a script that did nothing and exited, while the experiment that was actually in flight stayed
# dead.  The hook reported success every time: "queue relaunched: overnight".
#
# Visible in this session as gridstep advancing only 4 cells per restart, and only when a human
# noticed and relaunched it by hand.
#
# Take the first field, and treat the idle marker as "nothing to resume" rather than as a script
# name.
# harness/RESUME NAMES A CHAIN AND OUTRANKS CURRENT, WHICH NAMES ONE STAGE.
#
# CURRENT is the experiment LOCK -- it holds whichever single stage owns the box right now, and it
# goes to `idle` between stages.  Resuming from it therefore brings back one stage and drops
# everything queued behind it, because the waiters died with the container.  RESUME names the
# chain script instead, which re-enters its own stages and skips the cells that already exist.
Q="$(cut -d' ' -f1 harness/RESUME 2>/dev/null)"
[ -n "$Q" ] && [ -f "harness/$Q.sh" ] || Q="$(cut -d' ' -f1 harness/CURRENT 2>/dev/null || echo overnight)"
[ -n "$Q" ] && [ "$Q" != "idle" ] || Q=overnight
[ -f "harness/$Q.sh" ] || Q=overnight
[ -f "harness/$Q.sh" ] || exit 0
mkdir -p results
nohup bash "harness/$Q.sh" >> "results/$Q.log" 2>&1 < /dev/null &
echo "queue relaunched: $Q $(date -u +%H:%M:%S)"

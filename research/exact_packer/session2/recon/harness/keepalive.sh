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
# overnight.sh takes its own flock, so a second copy exits immediately and firing this
# repeatedly cannot stack.
set -u
cd "$(dirname "$0")/.." 2>/dev/null || exit 0
pgrep -f "harness/overnight\.sh" >/dev/null 2>&1 && exit 0
# the rewind takes local git back to a morning snapshot; re-sync before running anything
( cd ../../.. && git fetch -q origin claude/repair-plan-model-1ig6it 2>/dev/null \
  && git reset -q --hard FETCH_HEAD 2>/dev/null )
[ -f harness/overnight.sh ] || exit 0
mkdir -p results
nohup bash harness/overnight.sh >> results/tonight.log 2>&1 < /dev/null &
echo "queue relaunched $(date -u +%H:%M:%S)"

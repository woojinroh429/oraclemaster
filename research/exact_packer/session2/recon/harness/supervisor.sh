#!/bin/bash
# Keep the plan running, and keep the results reachable.
#
# Two things have interrupted work all session: the container resetting (five times, each one
# killing whatever queue was running) and individual runs dying on their own.  The sentinels in
# master.sh handle the first -- re-running it resumes -- but something has to notice a stopped
# queue and start it again, and something has to make sure the tree is whole before it does.
#
# So: every minute, if master.sh is not running and its plan is not finished, put the tree back
# (restore.sh is idempotent) and start it.  Also keep the log mirror alive, since without it a
# reset takes the night's numbers with it.
set -u
cd "$(dirname "$0")/.."
while true; do
  if ! pgrep -f '^/bin/bash .*harness/master\.sh' >/dev/null \
     && ! pgrep -f '^bash .*harness/master\.sh' >/dev/null; then
    if ! grep -q MASTER-PLAN-COMPLETE _n/master.log 2>/dev/null; then
      ./harness/restore.sh >> _n/supervisor.log 2>&1
      echo "[$(date -u +%H:%M:%S)] (re)starting master.sh" >> _n/supervisor.log
      setsid --fork bash ./harness/master.sh >/dev/null 2>&1 </dev/null
    fi
  fi
  if ! pgrep -f 'harness/keep\.sh' >/dev/null; then
    setsid --fork bash ./harness/keep.sh >/dev/null 2>&1 </dev/null
  fi
  sleep 60
done

#!/bin/bash
# qctl.sh {stop|start} <queue>   -- stop kills the queue and its in-flight cell; the cell's tag
# marker is a '# ' line and the resume check filters those out, so start re-runs it from scratch.
R=/home/user/oraclemaster/research/exact_packer/session2/recon
cd "$R" || exit 1
Q="${2:-integ}"
case "$1" in
  stop)
    for p in $(pgrep -x -f "bash harness/$Q.sh"); do kill "$p" 2>/dev/null; done
    sleep 1
    pkill -f 'run1.py myalgorithm' 2>/dev/null
    sleep 2
    echo "stopped $Q; run1 left: $(pgrep -cf 'run1.py myalgorithm' 2>/dev/null || echo 0)"
    ;;
  start)
    setsid nohup bash "harness/$Q.sh" > /dev/null 2>&1 < /dev/null &
    sleep 3
    echo "started $Q"
    ;;
esac

#!/bin/bash
# Stop any running integ queue, drop the a60.* cells taken before the axis-identity fix, restart.
R=/home/user/oraclemaster/research/exact_packer/session2/recon
cd "$R" || exit 1
for p in $(pgrep -x -f 'bash harness/integ.sh'); do kill "$p" 2>/dev/null; done
sleep 1
pkill -f 'run1.py myalgorithm' 2>/dev/null
sleep 2
grep -v 'a60\.' results/audit/integ.log > results/audit/integ.log.new
mv results/audit/integ.log.new results/audit/integ.log
setsid nohup bash harness/integ.sh > /dev/null 2>&1 < /dev/null &
sleep 3
echo "restarted; log lines now: $(wc -l < results/audit/integ.log)"

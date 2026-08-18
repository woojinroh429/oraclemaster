#!/bin/bash
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while pgrep -f "run1.py myalgorithm 1 240 .r1.p1.colstat" >/dev/null 2>&1; do sleep 10; done
pkill -f "harness/brkfast.sh" 2>/dev/null
sleep 2
exec bash harness/brkship.sh

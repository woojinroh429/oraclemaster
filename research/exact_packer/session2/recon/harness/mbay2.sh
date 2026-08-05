#!/bin/bash
# Multi-bay, now that the packer can reproduce its own input.
#
# The first attempt at this could not be judged: the warm start rebuilt the incumbent's layout at
# the wrong schedule, so the one-bay arm was losing residents it never meant to trade and the
# two-bay arm inherited the same defect.  With the entry matched, no-move is 15 of 32 calls -- the
# operator reproduces the incumbent and finds nothing better -- and a larger neighbourhood is the
# specific remedy for that.
#
# Paired from one incumbent per instance, so the difference is the neighbourhood.
set -u
cd "$(dirname "$0")/.." || exit 1
L=results/audit/mbay2.log
mkdir -p results/audit; touch $L
for p in 9 26 3 1 16 12 20 6; do
    grep -q "^P$p " $L 2>/dev/null && continue
    timeout 600 /usr/bin/python3.12 harness/mbay.py $p 30 60 3 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/mbay2.log \
      && git commit -q -m "in-flight: mbay2 P$p" ) >/dev/null 2>&1
done
echo "MBAY2DONE" >> $L
echo idle > "$(dirname "$0")/CURRENT"

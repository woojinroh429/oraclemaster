#!/bin/bash
# Multi-bay, now that the joint pack CONTAINS the one-bay pack.
#
# The previous run (results/audit/mbay3.log) came back 0 improvements of 8 against the one-bay
# arm's 7, and the reason was the neighbourhood rather than the idea.  The window was drawn from
# BOTH bays, so the target contributed fewer of its own residents than a one-bay call would take,
# the partner was sampled on a coarser grid, and the residents left out stood in the way as frozen
# obstacles.  A neighbourhood that is not a superset can be worse than the one it replaces, and it
# was, on every instance.
#
# The target bay now keeps ALL of its residents and the window applies only to the partner, so
# every selection the one-bay pack can make is available here and whatever the partner adds is
# extra.  On P16 that already returns a cross-bay move the one-bay pack cannot express.
#
# Paired from one incumbent per instance, so the difference is the neighbourhood.
set -u
cd "$(dirname "$0")/.." || exit 1
# NAME THIS QUEUE BEFORE RUNNING A SINGLE INSTANCE.  harness/keepalive.sh reads harness/CURRENT
# after a container restart and relaunches whatever it names, falling back to `overnight` when the
# file says something it cannot run.  Launching without writing it here is how a restart at 01:26
# resurrected a queue that had finished days earlier -- it failed on its first assertion and the
# machine sat idle while this experiment was gone.  Written and committed first, so the relauncher
# finds it even if the restart takes untracked files with it.
echo mbay3 > "$(dirname "$0")/CURRENT"
L=results/audit/mbay3.log
mkdir -p results/audit; touch $L
for p in 9 26 3 1 16 12 20 6; do
    grep -q "^P$p " $L 2>/dev/null && continue
    timeout 600 /usr/bin/python3.12 harness/mbay.py $p 30 60 3 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/mbay3.log \
      && git commit -q -m "in-flight: mbay3 P$p" ) >/dev/null 2>&1
done
echo "MBAY3DONE" >> $L
echo idle > "$(dirname "$0")/CURRENT"

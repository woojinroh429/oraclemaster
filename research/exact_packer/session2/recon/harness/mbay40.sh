#!/bin/bash
# Does the two-bay repacking neighbourhood pay, across the whole set?
#
# The direct probe (harness/mbay.py) answers whether the larger neighbourhood finds moves the
# one-bay one cannot, from a single incumbent.  That is the right first question and it is not
# this one.  This is the question that decides whether it SHIPS: run the real algorithm end to
# end, once with OGC_BRKBAYS=1 and once with 2, on the same instance at the same budget, and read
# the objective the grader reports.
#
# Paired and interleaved, because run-to-run variance on an unchanged build has measured 3.2% to
# 32% depending on the instance -- a difference smaller than that is not a difference, and an
# unpaired sweep cannot tell them apart.  Instances are ordered so a log truncated by a container
# wipe is still balanced across sizes and across bay counts: the two-bay instances (where the
# joint pack is the whole yard and the window matters most) are interleaved with the four- and
# five-bay ones rather than grouped.
#
# BRK_DEBUG stays OFF.  It costs nothing but it puts the tier trace in the log, and the log is
# what gets read later; the per-call detail belongs in the direct probe where it can be looked at
# against a known incumbent.
set -u
cd "$(dirname "$0")/.." || exit 1
L=results/audit/mbay40.log
mkdir -p results/audit
touch $L

run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       echo "# [$1]" >> $L
       env $3 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1
       ( cd "$(git rev-parse --show-toplevel)" \
         && git add research/exact_packer/session2/recon/results/audit/mbay40.log \
         && git commit -q -m "in-flight: mbay40 $1" ) >/dev/null 2>&1 ; }

# bays=2 first (13 25 26 36 40 5 10 21 33 37 39), then the rest, interleaved by size.
for p in 13 3 25 12 26 6 36 30 40 16 5 4 10 23 21 34 33 11 37 14 39 28 \
         1 2 7 8 9 15 17 18 19 20 22 24 27 29 31 32 35 38; do
    run "one.$p" $p "OGC_BRKBAYS=1"
    run "two.$p" $p "OGC_BRKBAYS=2"
done
echo "MBAY40DONE $(grep -c '^P' $L)"
echo idle > "$(dirname "$0")/CURRENT"   # do not let the restart hook re-run a finished queue

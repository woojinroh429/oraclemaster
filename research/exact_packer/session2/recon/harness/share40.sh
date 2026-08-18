#!/bin/bash
# Does restarting a hopelessly-behind worker beat leaving it alone?  Forty paired instances.
#
# The four workers are independent and combined only by a final minimum, so a bad one costs
# nothing in the answer and went unnoticed for that reason.  Measured per worker
# (results/audit/wstat.md) P7's control returned 937,453 / 923,531 / 1,196,169 / 2,932,676: one
# core spent the whole budget 3.2x behind the winner.  OGC_SHARE=1 lets such a worker publish its
# incumbent, see that it is more than OGC_SHAREGAP behind the best other, and rebuild from a fresh
# seed -- once, in the middle third of the run, and only when the gap is large.
#
# This one touches the SEARCH, unlike the tail experiments, so it moves every instance and not
# only the bad ones.  A change that reshuffles the trajectory has been worth -7.7% before, which
# is why this needs the full forty rather than a sample.
#
# WSTAT stays on in both arms: the per-worker values are what say whether a restart fired at all
# and whether it turned a wasted core into a usable draw.
set -u
cd "$(dirname "$0")/.." || exit 1
L=results/audit/share40.log
mkdir -p results/audit
touch $L

run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       echo "# [$1]" >> $L
       env $3 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1
       ( cd "$(git rev-parse --show-toplevel)" \
         && git add research/exact_packer/session2/recon/results/audit/share40.log \
         && git commit -q -m "in-flight: share40 $1" ) >/dev/null 2>&1 ; }

# Sizes interleaved so a truncated log stays balanced; the instances wstat already measured come
# first, so their per-worker numbers can be compared directly against the fixed portfolio.
for p in 7 25 22 13 1 36 5 20 \
         2 3 4 6 8 9 10 11 12 14 15 16 17 18 19 21 23 24 26 27 28 29 30 31 32 33 34 35 37 38 39 40; do
    run "fix.$p" $p "OGC_NOTHING=1"
    run "shr.$p" $p "OGC_SHARE=1"
done
echo "SHARE40DONE $(grep -c '^P' $L)"
echo idle > "$(dirname "$0")/CURRENT"   # do not let the restart hook re-run a finished queue

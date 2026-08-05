#!/bin/bash
# Paired one-bay vs two-bay repacking, from the SAME incumbent, across the bay-count range.
#
# This is the direct probe, not the shipping question.  Both arms are handed one finished solution
# and asked to improve it, so the difference between them is the neighbourhood and nothing else --
# no solve variance, no scheduler, no bandit.  That is what makes a 0.1% reading mean something on
# a set where run-to-run variance is 3.2% to 32%.
#
# Ordered by bay count so a truncated log still covers the range: the two-bay instances (where the
# joint pack is the whole yard and almost every resident is stuck) alternate with the four- and
# five-bay ones (where there is somewhere to be evicted to and the two arms should differ least).
set -u
cd "$(dirname "$0")/.." || exit 1
L=results/audit/mbayq.log
mkdir -p results/audit
touch $L

run(){ grep -q "^P$1 " $L 2>/dev/null && return
       echo "# probe $1" >> $L
       BRK_DEBUG=1 timeout 600 /usr/bin/python3.12 harness/mbay.py "$1" 30 60 2 >> $L 2>&1
       ( cd "$(git rev-parse --show-toplevel)" \
         && git add research/exact_packer/session2/recon/results/audit/mbayq.log \
         && git commit -q -m "in-flight: mbayq P$1" ) >/dev/null 2>&1 ; }

for p in 3 13 20 12 25 6 16 26 4 36 30 40 11 5 23 33 14 21 34 37; do run $p; done
echo "MBAYQDONE"
echo idle > "$(dirname "$0")/CURRENT"

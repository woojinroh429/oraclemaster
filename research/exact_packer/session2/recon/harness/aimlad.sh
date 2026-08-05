#!/bin/bash
# Spread the four workers across the aim range instead of stacking them on its two ends.
#
# Adopted:  0.90 0.10 0.90 0.10   (two workers at each extreme)
# Ladder :  0.90 0.60 0.30 0.10   (one worker at each of four settings)
#
# The sweep in results/audit/aim.md is monotone in aim on large instances and monotone the other
# way on small ones, so the mid settings are dominated when used ALONE.  That says nothing about
# their value in a portfolio whose answer is the minimum: a 0.60 worker can win an instance where
# 0.90 finishes too slowly and 0.10 is too narrow, and neither end covers that case.
#
# Paired, same instance, same budget, one run per arm.  Instances alternate small/large so a
# truncated log is still a balanced sample -- every restart today has cost the tail of a queue.
set -u
cd "$(dirname "$0")/.." || exit 1
L=results/audit/aimlad.log
mkdir -p results/audit
touch $L

run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       env $3 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1
       ( cd ../../.. && git add research/exact_packer/session2/recon/results/audit/aimlad.log \
         && git commit -q -m "in-flight: aimlad $1" ) >/dev/null 2>&1 ; }

for p in 7 13 22 25 1 36 5 20 3 30 11 2 9 4 27 38; do
    run "mix.$p" $p "OGC_NOTHING=1"
    run "lad.$p" $p "OGC_AIMSET=0.90,0.60,0.30,0.10"
done
echo "AIMLADDONE $(grep -c '^P' $L)"

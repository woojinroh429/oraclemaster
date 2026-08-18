#!/bin/bash
# The aim sweep has no floor yet: 0.45 is best on all four, including the one that looked flat.
#
#     inst    0.90         0.75         0.60         0.45
#     P25   83,469,231   82,453,266   80,233,515   77,800,747
#     P13   75,460,745   75,140,944   73,896,944   72,861,873
#     P36   89,254,771   87,320,348   87,949,656   84,214,242
#     P20   10,553,084   10,796,210   10,728,208    9,826,336
#
# Keep going down.  If it is still falling at 0.10 then the beam is not producing the answer at
# all -- it is producing a STARTING POINT for the contact rollout, and everything arranged around
# letting it finish has been arranging the wrong thing.
cd "$(dirname "$0")/.."
L=results/audit/aim.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       OGC_BEAMAIM=$3 timeout 500 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1; }
for a in 0.30 0.20 0.10; do
  for p in 25 13 36 20; do run "a$a.$p" $p $a; done
done
echo "AIM2DONE $(date -u +%H:%M)" >> $L

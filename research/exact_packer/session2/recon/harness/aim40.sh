#!/bin/bash
# The last gate: does AIM=0.10 hold across all forty, or only on the four large ones?
#
#     inst    0.90         0.45         0.30         0.20         0.10     vs 0.90
#     P25   83,469,231   77,800,747   72,005,889   69,865,266   68,973,666  -17.4%
#     P13   75,460,745   72,861,873   70,889,073   68,648,923   66,618,791  -11.7%
#     P36   89,254,771   84,214,242   82,428,479   75,600,230   73,339,019  -17.8%
#     P20   10,553,084    9,826,336    9,897,771    9,543,763    9,255,809  -12.3%
#
# Against the SHIPPED build those are -22% to -24%.  But all four are 250-300 blocks, which is
# exactly where the beam was passing its deadline; on 150-block instances it finishes, the
# salvage never runs, and a lower aim can only narrow the beam -- pure loss.  Half the set is
# that size.  If the small instances lose more than the large ones win, this does not ship.
#
# Paired, both arms at 180 s, 0.90 (today's behaviour) against 0.10.
cd "$(dirname "$0")/.."
L=results/audit/aim40.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       OGC_BEAMAIM=$3 timeout 600 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1; }
for p in $(seq 1 40); do
  run "hi.$p" $p 0.90
  run "lo.$p" $p 0.10
done
echo "AIM40DONE $(date -u +%H:%M)" >> $L

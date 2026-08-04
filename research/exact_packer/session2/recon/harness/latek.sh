#!/bin/bash
# Does a ladder of late windows rescue the instances a single break-even window loses on?
#
# WHY IT SHOULD.  price(d) = gain - w1*d falls with the delay, so a seat offered AT break-even is
# worth nothing by construction.  One window was all the per-block weight could price, so it went
# to the widest opening; per-seat prices remove that constraint, and the ladder d, d/2, d/4 lets
# the solver take the cheapest delay that actually frees the bay.
#
# The ten losers lead, because that is where the claim has to hold.  Six winners follow, because a
# change that rescues the losers by giving back the wins is not an improvement.  LATEK=1 reproduces
# today's single window exactly, so the two arms differ only in the ladder.
cd "$(dirname "$0")/.."
L=results/audit/latek.log; touch $L
run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       OGC_LATEK=$3 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1; }
for p in 38 14 20 19 29 3 25 36 32 6   37 24 10 35 15 17; do
  run "k1.$p" $p 1
  run "k3.$p" $p 3
done
echo "LATEKDONE $(date -u +%H:%M)" >> $L

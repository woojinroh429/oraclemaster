#!/bin/bash
# SETTLE OGC_BCAP ON ITS OWN, AT FIVE PAIRS, BEFORE ANYTHING IS WRITTEN ABOUT IT.
#
# prob_16 at 240 s, two draws per arm:
#
#     stock                     3,010,278  3,179,204   mean 3,094,741   span  5.6%
#     OGC_BCAP=137              3,018,252  2,714,034   mean 2,866,143   span 11.2%   -7.4%
#     OGC_AXIS=2 + BCAP=137     2,725,778  2,913,538   mean 2,819,658   span  6.9%   -8.9%
#
# The axis pin adds 1.5 points over the ceiling alone and costs the entire portfolio, so the ceiling
# alone is the change worth settling.  It is one constant, it keeps rotation, it predicts nothing.
#
# EVERY NUMBER ABOVE IS TWO DRAWS AGAINST SPANS OF 7-11%, WHICH IS NOTHING.  Seven claims this
# session were written at one or two draws and overturned by the next -- including both readings of
# this very arm, which went -2.5% then -7.4% on consecutive cells.  Five pairs per instance, and no
# verdict before they are all in.
#
# WHY THE CEILING COULD BE WRONG.  myalgorithm.py's OGC_BEAMCAP comment measured the opposite
# direction on this same instance: "wider draws are better on average and worse at the minimum, and
# the minimum is what gets reported", from 20 draws at ask=47.2 s scoring a worse best than 8 draws
# at ask=11.2 s.  A higher ceiling is more width, so if that reading is the dominant one the arm
# should lose at five pairs even though it leads at two.  One of the two is about to be wrong.
#
# prob_4 IS THE INSTANCE THAT DECIDES WHETHER IT SHIPS.  prob_16 is where axis 2 dominates and
# where width was measured; prob_4 is a same-scale instance where it does not.  A ceiling raise is
# global -- every axis on every instance gets it -- so a gain confined to prob_16 is instance
# fitting and must not ship.  Three pairs there, run second, and prob_1 last as a third shape.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo bcap > harness/CURRENT
L=results/audit/bcap.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/bcap.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/bcap.sh \
        && git commit -q -m "in-flight: bcap $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_WSTAT=1 timeout 560 /usr/bin/python3.12 harness/run1.py myalgorithm $2 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4 5; do
  run "c.p16.stock.r$rep" 16 "WORKERS=4"
  run "c.p16.b137.r$rep"  16 "WORKERS=4 OGC_BCAP=137"
done
echo "== BCAP prob_16 done ==" >> $L
for rep in 1 2 3; do
  run "c.p4.stock.r$rep" 4 "WORKERS=4"
  run "c.p4.b137.r$rep"  4 "WORKERS=4 OGC_BCAP=137"
done
echo "== BCAP prob_4 done ==" >> $L
for rep in 1 2 3; do
  run "c.p1.stock.r$rep" 1 "WORKERS=4"
  run "c.p1.b137.r$rep"  1 "WORKERS=4 OGC_BCAP=137"
done
echo "BCAPDONE" >> $L
echo idle > harness/CURRENT

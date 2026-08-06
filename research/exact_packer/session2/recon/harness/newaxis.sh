#!/bin/bash
# Put the missing idea into the portfolio -- and find out what it should cost.
#
# The gap, stated precisely: the six shipped axes carry defer_big x3, lst, edd, big_first, and not
# one of them blends deadline urgency with size.  Both unused orders that won an instance in
# orders replicate 1 are exactly that blend -- rank is due-rank + area-rank, sac3 is rank plus
# "dispatch the three largest area*time blocks last".  sac3 beat all six axes by 17.09% on P16 and
# rank beat them by 6.63% on P6.  The three defer_big entries were best on nothing.
#
# The design question is not whether to add it but WHAT IT REPLACES, and the data already argues
# against appending: base lost 3 of 4 instances to a single fixed order, and bandit priced the
# reason -- choosing among six costs 1-9% against spending the whole budget on one.  A seventh
# axis charges that toll on every instance to buy P16.
#
#   arm  base   the shipped six
#   arm  v1     defer_big[5] -> sac3            (six axes, one order swapped)
#   arm  v2     defer_big[5] -> sac3, [1] -> rank (six axes, two swapped)
#   arm  v3     the six PLUS sac3               (seven axes -- prices the toll directly)
#
# v3 is the control that makes v1 and v2 readable.  If v3 matches v1 then the extra axis is free
# and replacing was unnecessary; if v3 is worse then the toll is real and the slot has to be
# bought from somewhere, which is what v1 and v2 do.
#
# Eight instances, not the four the orders run used: a swap that helps P16 and hurts four others
# is a loss, and four instances cannot show that.  Rep-major, 60 s, real grader path.
set -u
cd "$(dirname "$0")/.." || exit 1
echo newaxis > harness/CURRENT
L=results/audit/newaxis.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -q "\[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/newaxis.log \
      && git commit -q -m "in-flight: newaxis $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 1 12 16 26 6 3 20 30; do
        run $rep base $p ""
        run $rep v1   $p "OGC_AXSET=v1"
        run $rep v2   $p "OGC_AXSET=v2"
        run $rep v3   $p "OGC_AXSET=v3"
    done
    echo "REPDONE $rep" >> $L
done
echo "NEWAXISDONE" >> $L
echo idle > harness/CURRENT

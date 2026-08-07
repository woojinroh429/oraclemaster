#!/bin/bash
# ARE THE TWELVE-ORIENTATION INSTANCES THROUGHPUT-STARVED?
#
# best_cell_contact_tl loops every orientation a block has, with no cap and no early exit:
#
#     int norient = (int)bs.orients.size();
#     for(int oi=0; oi<norient; oi++){ ... }
#
# so a twelve-orientation block costs about 1.5x an eight-orientation one in the position scan.
# Ten of the forty stage-2 instances carry twelve, and results/audit/instances.md records that the
# preliminary set had nothing at that level -- which is where every axis parameter was tuned.
#
# The beam's width controller sets Bcur from measured seconds per state, so a scan that costs 1.5x
# buys 1/1.5 the width in the same budget.  If that is what happens, the twelve-orientation
# instances should SALVAGE more (the beam runs past its deadline) and CAP less (it never reaches
# the width it asked for).  Both are already tracked by the engine and neither has ever been
# logged; OGC_BEAMSTAT=1 prints them.
#
# Matched on block count so size cannot explain the difference:
#
#     150 blocks   prob_1  (12 orientations)   vs  prob_7  (8)
#     200 blocks   prob_3  (12)                vs  prob_9  (8)
#     250 blocks   prob_4  (12)                vs  prob_2  (8)
#     150 blocks   prob_21 (12)                vs  prob_5  (8)
#
# This measures the beam's behaviour, not the objective -- whether the extra orientations are being
# paid for in width.  If they are, capping the orientation scan is a real lever; if the two groups
# salvage and cap alike, the hypothesis is dead and costs nothing further.
set -u
cd "$(dirname "$0")/.." || exit 1
echo orcost > harness/CURRENT
L=results/audit/orcost.log
mkdir -p results/audit; touch $L

run(){ # prob
    local tag="or.$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_BEAMSTAT=1 OGC_POLISH=1 OGC_WSTAT=1 timeout 1200 /usr/bin/python3.12 harness/run1.py \
        myalgorithm $1 240 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$1 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/orcost.log \
      && git commit -q -m "in-flight: orcost $tag" ) >/dev/null 2>&1
}

for p in 1 7 3 9 4 2 21 5; do
    run $p
done
echo "ORCOSTDONE" >> $L
echo idle > harness/CURRENT

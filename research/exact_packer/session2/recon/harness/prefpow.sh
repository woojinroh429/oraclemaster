#!/bin/bash
# BEND THE PENALTY PER BLOCK INSTEAD OF TOLLING EVERY BLOCK ALIKE.
#
# The uniform toll is closed.  OGC_CPANCHW adds the same constant to every block's planned bay,
# which tells the search "nobody may move", and the measurements are a straight line:
#
#     toll     obj         Z1    Z3
#        0     515,188     25    543
#      100     703,795     58    493
#      300   1,849,481    254    212
#
# Eight tardiness units bought per preference unit.  The instance had already said why that is the
# wrong shape: at a first-choice assignment the two small bays sit at 147% and 201% of their area
# at the peak, so roughly 983 area units MUST be displaced and the only free variable is WHICH
# blocks go.  A uniform toll answers "none of them", which is not one of the available answers.
#
# The objective is LINEAR in preference regret, and a sequential search under-protects the
# expensive end of that line: on a real incumbent the displaced blocks cost 98, 96, 90 and 84 each
# while blocks with regret 6, 7, 10 and 16 -- with MORE area than them -- kept their first choice.
#
# OGC_PREFPOW re-expresses every penalty as R*(pen/R)^gamma, R the median across blocks of each
# block's largest penalty (61 on this instance).  Scale is held: a block at the typical regret
# keeps the penalty it had, and only the SPREAD moves.  At gamma = 1.5:
#
#     blk  29   true 98, 99, 0   ->   124, 126, 0
#     blk  76   true 96, 92, 0   ->   120, 113, 0
#     blk 148   true 90, 95, 0   ->   109, 119, 0
#     blk  51   true  6,  0, 29  ->     2,   0, 20
#     blk  30   true  7, 16, 0   ->     2,   8, 0
#     blk  67   true 10,  0, 46  ->     4,   0, 40
#
# The three at the top are the incumbent's worst payers; the three at the bottom are the blocks
# the greedy-spill argument names as the right victims, and they become nearly free to move.
#
# HOLDING SCALE IS WHAT MAKES THIS NOT A DISGUISED w3mul.  Without the R normalisation gamma > 1
# would inflate every penalty at once, which is the w3mul sweep, and that closed unresolvable at
# twelve draws per cell.
#
# WHAT WOULD MAKE IT FAIL, named first.  The search now optimises something the scorer does not: a
# regret-10 block is nearly free to displace even where the true objective would rather keep it.
# Too high a gamma should show Z3 climbing again from the CHEAP end while the expensive end stays
# protected -- so Z3 is read alongside the total, and a total that improves while Z3 worsens means
# the gain came from Z1 and the mechanism is not the one claimed.
#
# SHIPPED RIG, not the uniform one: this is a candidate to ship, so it is measured in the
# configuration that would ship it.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo prefpow > harness/CURRENT
L=results/audit/prefpow.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/prefpow.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/prefpow.sh \
        && git commit -q -m "in-flight: prefpow $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  for G in 1.0 1.3 1.6 2.0 2.5; do
    run "pp.$G.r$rep" "WORKERS=4 OGC_PREFPOW=$G"
  done
done
echo "PREFPOWDONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# DOES THE w3mul WIN SURVIVE THE SHIPPED PORTFOLIO?  THE SWEEP DELIBERATELY IS NOT THE SHIPPED RUN.
#
# w3sweep.sh runs FOUR IDENTICAL config-A workers so that contention is constant and w3mul is the
# only free variable.  That is the right design for asking which direction w3mul should move, and
# the wrong one for asking what shipping it would do.  The shipped run is two config-A workers and
# two cheap config-B ones, the answer is a MINIMUM over them, and w3mul reaches config A through
# OGC_DIRSET=2's setdefault -- which an env-set OGC_W3MUL overrides for EVERY worker, config B
# included.
#
# So a win in the sweep can fail here three ways, and each is worth naming before the numbers land:
#
#   the minimum absorbs it   four A workers all improving moves the mean; two of four moving does
#                            not have to move the min, which is what nw2 already showed when
#                            widening one worker (OGC_BMULSET) came out +1.4% over five pairs
#   config B changes too     B gets the new w3mul as well; B has never won a draw on prob_1 in 388
#                            tries, but its COST is a resource -- axprod showed making B heavier
#                            degrades the A workers by taking their cores
#   the sweep is one draw    every cell is n=1 so far, against a 13% control span at this budget
#
# CELLS.  Shipped configuration untouched except OGC_W3MUL, five pairs, 120 s:
#
#     0.5   what ships today (DIRSET=2 sets it; naming it explicitly changes B too, so this is the
#           control for the OTHER cells rather than a replica of production -- production is the
#           `stock` cell, which sets nothing)
#     2.0   the sweep's first clear winner
#     4.0   the sweep's best
#
# `stock` is included as a fourth arm precisely because 0.5-explicit and stock differ on config B,
# and if those two disagree then the whole comparison is measuring B and not w3mul.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo w3ship > harness/CURRENT
L=results/audit/w3ship.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/w3ship.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/w3ship.sh \
        && git commit -q -m "in-flight: w3ship $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4 5; do
  run "s.stock.r$rep" "WORKERS=4"
  run "s.w0_5.r$rep"  "WORKERS=4 OGC_W3MUL=0.5"
  run "s.w2_0.r$rep"  "WORKERS=4 OGC_W3MUL=2.0"
  run "s.w4_0.r$rep"  "WORKERS=4 OGC_W3MUL=4.0"
done
echo "W3SHIPDONE" >> $L
echo idle > harness/CURRENT

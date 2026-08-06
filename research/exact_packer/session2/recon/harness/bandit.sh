#!/bin/bash
# Does the bandit find the best axis inside 60 s, or is selection the thing that is broken?
#
# WHY THIS COMES BEFORE DESIGNING BETTER ORDERS.  cdecomp settled that the axis config decides
# which valley construction reaches -- five instances, config spread 32% to 210% against a control
# of 0.0% to 12.6%.  The obvious next move is to design better dispatch orders.  That move is
# worthless if the selection cannot pick them: every worker already receives all six configs, so a
# seventh good one changes nothing unless the bandit reaches it.  Cheaper to check first, and it
# decides which of two quite different jobs is worth doing.
#
#   arm  ax0..ax5   OGC_AXIS=k pins every worker to _AXES[k] for the whole run
#   arm  free       the shipped default: all six, bandit chooses
#
# min(ax0..ax5) is what perfect selection would have returned, since a pinned run spends the
# entire budget on that one config.  `free` is what the bandit actually returns.  The gap between
# them is the price of selection.
#
#   gap near zero   selection works; the lever is genuinely better configs, and that is the job
#   gap large       selection is the failure.  Adding configs is pointless until it is fixed,
#                   and fixing it is much cheaper than redesigning construction
#
# Note what this comparison is NOT: min(ax0..ax5) is not achievable in one run, because choosing
# needs the trying.  It is an upper bound on what selection could ever be worth -- which is the
# right thing to size the work against before doing any of it.
#
# Rep-major so an early stop leaves a balanced set; full 60 s budget, real grader path.
set -u
cd "$(dirname "$0")/.." || exit 1
echo bandit > harness/CURRENT
L=results/audit/bandit.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob envassign
    local tag="r$1.$2.$3"
    grep -q "\[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/bandit.log \
      && git commit -q -m "in-flight: bandit $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 20 16 1 6; do
        run $rep free $p ""
        for k in 0 1 2 3 4 5; do
            run $rep "ax$k" $p "OGC_AXIS=$k"
        done
    done
    echo "REPDONE $rep" >> $L
done
echo "BANDITDONE" >> $L
echo idle > harness/CURRENT

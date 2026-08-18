#!/bin/bash
# IS THE PERMUTATION THE 18% LEVER?  Measured with machinery that already exists and has never run.
#
# ogc_fast.cpp's contact_beam places order[level] in every beam state, so every state at level k
# holds the same block SET.  Its own dedup comment records the consequence: "MEASURED INERT ...
# our beam uses a FIXED dispatch order ... The reference needs this because its orders vary."
#
# _draw_order samples a permutation -- repeatedly a uniform pick from the top-k remaining under the
# axis's priority -- and _beam_once uses it whenever cfg["dk"] > 1.  All six axes ship dk=0.  Since
# the operator loop calls the beam many times per worker, dk>1 makes a run a best-of-N over
# permutations for free, which prices the idea before anyone touches the C++.
#
# Arms are the window width:
#     k=1  today (fixed order; OGC_DK unset)
#     k=2  adjacent swaps only
#     k=3
#     k=5  wide enough that the axis's priority is a bias rather than a rule
#
# Sizes matter here in a way they have not elsewhere: a wider window costs nothing per beam call
# but makes each drawn order worse on average, so the question is whether best-of-N over sampled
# permutations beats one good permutation.  That is the same shape as every budget-reallocation
# arm that lost this session -- more draws, each weaker -- and the reason to expect a different
# answer is that those traded DEPTH while this trades only the ordering heuristic's sharpness.
#
# Six instances spanning the exchange-rate range, 240 s, two replicates, paired on the instance.
set -u
cd "$(dirname "$0")/.." || exit 1
echo perm > harness/CURRENT
L=results/audit/perm.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py myalg_perm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/perm.log \
      && git commit -q -m "in-flight: perm $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
    for p in 20 4 13 26 2 6; do
        run $rep k1 $p ""
        run $rep k2 $p "OGC_DK=2"
        run $rep k3 $p "OGC_DK=3"
        run $rep k5 $p "OGC_DK=5"
    done
    echo "REPDONE $rep" >> $L
done
echo "PERMDONE" >> $L
echo idle > harness/CURRENT

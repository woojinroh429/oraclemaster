#!/bin/bash
# THE PERMUTATION SEARCH ITSELF, IN THE BEAM, WITH DEPTH UNCHANGED.
#
# ogc_fast.cpp used to place order[level] in every beam state, so every state at level k held the
# same block SET and differed only in placements.  Its own dedup comment recorded the consequence
# and called itself dead code: "our beam uses a FIXED dispatch order ... The reference needs this
# because its orders vary."
#
# Each state now expands the CBMCAND earliest UNPLACED blocks under its axis's priority, so states
# diverge in which blocks they have placed and the permutation becomes part of the search.
# OGC_MCAND=1 is the old code path exactly.
#
# WHAT IS AND IS NOT TRADED.  Every state still places one block per level and the beam still keeps
# B survivors, so no worker loses depth -- the thing that killed ROUNDS, the redraw and the aim
# race's second phase.  What grows is branching: m times as many children per level, competing for
# the same B slots.  So the bet is that a permutation worth finding is worth more than the
# placement diversity those slots were holding.
#
# First draws on prob_24 at 60 s: m=1 2,631,837, m=2 2,943,281.  One draw each on the noisiest
# possible budget, and m=2 is 11.8% worse -- which is exactly what it looks like if the extra
# permutations are not paying for the width they displace.  That is the question, and it needs a
# paired set rather than a smoke.
#
# Also runs DEDUP off against on at m=3.  Under a fixed order the dedup was measured identical to
# the last digit on five instances; if it now changes the answer, states really are reaching the
# same layout by different orders, which is the structural claim behind the whole change.
set -u
cd "$(dirname "$0")/.." || exit 1
echo mcand > harness/CURRENT
L=results/audit/mcand.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/mcand.log \
      && git commit -q -m "in-flight: mcand $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
    for p in 24 4 20 26 13 6; do
        run $rep m1  $p "OGC_MCAND=1"
        run $rep m2  $p "OGC_MCAND=2"
        run $rep m3  $p "OGC_MCAND=3"
        run $rep m3nd $p "OGC_MCAND=3 OGC_DEDUP=0"
    done
    echo "REPDONE $rep" >> $L
done
echo "MCANDDONE" >> $L
echo idle > harness/CURRENT

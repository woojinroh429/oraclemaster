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
# The DEDUP-off arm has already done its job and is retired: under a fixed order the dedup was
# identical to the last digit on five instances, and with branching on it moved prob_24 by 1.7%
# (2,905,816 -> 2,857,312) and prob_4 by 9.8% (2,829,562 -> 2,577,614).  States really do reach the
# same layout by different orders now, which is the structural claim behind the whole change and
# was not previously possible.
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
        # DID m=3 LOSE TO THE BRANCHING, OR TO THE SLOT SHORTAGE IT CAUSES?
        #
        # m times as many children compete for the same B survivor slots, so the effective width
        # per block-set falls to B/m.  m=2 won on prob_24 and prob_4 (-14.50%, -3.74%) and m=3 lost
        # both (+2.40%, +10.89%), and on both the worker spread peaked at m=2 and then collapsed
        # BELOW the m=1 baseline at m=3 -- 5.9/13.5/8.4% and 19.5/25.9/9.2%.  A search running out
        # of width looks exactly like that.
        #
        # So give the width back in proportion.  OGC_BCAP was the hard 96 ceiling inside
        # _beam_width, and ogc_fast's own instrumentation says it binds: beam_width_capped_ is
        # (Bcur >= Bmax) and Bmax is precisely what _beam_width returns, so three of the six axes
        # (Bmul 1.0, 1.4, 1.0) were pinned there whatever the budget allowed.
        #
        # The adaptive controller still refuses width it cannot afford, so a larger ceiling costs
        # nothing on instances with no time for it -- these arms ask for width, they do not force it.
        run $rep m2w $p "OGC_MCAND=2 OGC_BCAP=192"
        run $rep m3w $p "OGC_MCAND=3 OGC_BCAP=288"
    done
    echo "REPDONE $rep" >> $L
done
echo "MCANDDONE" >> $L
echo idle > harness/CURRENT

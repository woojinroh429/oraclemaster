#!/bin/bash
# EVERYTHING INTO THE BEAM.  Polish off, branching and width pushed as far as they pay.
#
# Two measurements set the direction.
#
# The final polish earns nothing: across 804 runs its median gain is 0.00% and 419 of them gained
# NOTHING, for a reservation of min(20% of budget, 40 s).  It is off by default now and the reserve
# it held goes to the workers -- about 19% more search at a 240 s limit.
#
# And the construction responds to branching PROVIDED the width comes with it.  Beam-side, against
# the m1 baseline:
#
#     m2   (branch 2, width as shipped)   -4.42%  / -3.59%     spread 13.5% / 25.9%
#     m3   (branch 3, width as shipped)   +3.00%  / +10.88%    spread  8.4% /  9.2%
#     m3w  (branch 3, width x3)           -6.46%               spread 15.6%
#
# m3 and m3w differ only in the ceiling and they are 9.5 points apart, so m3 lost to the slot
# shortage its own branching caused, not to the permutations.  (This session withdrew that
# hypothesis once on the strength of m2w, and m2w turned out to be a polish artefact: beam-side it
# is 0.2% from m2, not 11.5% worse.  Beam-side numbers only from here.)
#
# So the arms escalate branch and width together, and each is a REQUEST -- the adaptive controller
# still refuses width it cannot afford, so an instance with no time for it pays nothing.
#
#     ship   the shipped build, polish ON, no branching     <- what any change has to beat
#     m1     polish off, no branching                       <- isolates the polish removal
#     m3w    branch 3, width x3
#     m4w    branch 4, width x4
#     m6w    branch 6, width x6
#
# `ship` and `m1` together separate the two changes, which the earlier queues did not do.
set -u
cd "$(dirname "$0")/.." || exit 1
echo beamhard > harness/CURRENT
L=results/audit/beamhard.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 1200 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/beamhard.log \
      && git commit -q -m "in-flight: beamhard $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
    for p in 24 4 20 26 13 6; do
        run $rep ship $p "OGC_POLISH=1 OGC_MCAND=1"
        run $rep m1   $p "OGC_MCAND=1"
        run $rep m3w  $p "OGC_MCAND=3 OGC_BCAP=288"
        run $rep m4w  $p "OGC_MCAND=4 OGC_BCAP=384"
        run $rep m6w  $p "OGC_MCAND=6 OGC_BCAP=576"
    done
    echo "REPDONE $rep" >> $L
done
echo "BEAMHARDDONE" >> $L
echo idle > harness/CURRENT

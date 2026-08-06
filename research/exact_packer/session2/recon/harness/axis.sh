#!/bin/bash
# Collect worker-by-worker objectives with wid order intact, so the portfolio can be audited.
#
# Everything measured so far treats the four workers as an anonymous sample.  They are not: wid
# fixes the beam aim (even workers 0.90, odd 0.10), the axis rotation and the seed.  If the same
# wid loses on every instance then three quarters of the machine is producing draws the answer
# never keeps, and that is a lever on the bad run -- not by adding draws, which rounds has just
# shown does not pay, but by making the draws we already have less alike.
#
# NEW DATA IS REQUIRED.  The logs already on disk were written while _pool_round returned results
# in completion order, so their WSTAT columns do not correspond to wid and no amount of care in
# the reader can recover it.  This is the first collection since da48660 restored the ordering.
#
# R=1 only and the shipped defaults throughout -- the question is what the portfolio does as it
# actually runs, not under a knob.  Rep-major so an early stop leaves a balanced set.
set -u
cd "$(dirname "$0")/.." || exit 1
echo axis > harness/CURRENT
L=results/audit/axis.log
mkdir -p results/audit; touch $L

for rep in 1 2 3 4 5; do
    for p in 1 12 16 26 6 3 20 30; do
        tag="r$rep.axis.$p"
        grep -q "\[$tag\]" $L 2>/dev/null && continue
        echo "# [$tag]" >> $L
        OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 "[$tag]" \
            --data data/stage2 >> $L 2>&1
        ( cd "$(git rev-parse --show-toplevel)" \
          && git add research/exact_packer/session2/recon/results/audit/axis.log \
          && git commit -q -m "in-flight: axis $tag" ) >/dev/null 2>&1
    done
    echo "REPDONE $rep" >> $L
done
echo "AXISDONE" >> $L
echo idle > harness/CURRENT

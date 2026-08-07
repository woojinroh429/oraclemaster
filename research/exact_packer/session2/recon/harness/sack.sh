#!/bin/bash
# How many blocks should sacK actually sacrifice?
#
# sac3 beat the whole six-axis portfolio by 17.09% and 16.98% on P16, on a base that returned the
# identical objective both times.  The gain is real.  The 3 is not measured -- I picked it writing
# the arm, and the code parses whatever digits follow "sac", so K is a free parameter that has
# never been looked at.
#
# This has to run BEFORE newaxis.  newaxis decides whether the blend replaces a defer_big slot or
# is appended, and it decides that by how much the blend is worth; carrying a suboptimal K into
# that comparison would answer the question about the wrong candidate.
#
# K is the count of blocks pushed to the back of the dispatch, ranked by area*processing_time --
# the yard-time each one occupies.  Too few and the obstruction remains; too many and their
# tardiness outweighs the room they free.  The instances span 150 to 300 blocks, so if the right K
# scales with n rather than being a constant, that shows up as different instances preferring
# different rungs -- which would be a finding in itself and would rule out a single shipped K.
#
# sac0 is not a thing (the code would sacrifice nobody and reduce to rank), so rank IS the K=0
# rung and is included to anchor the low end.
set -u
cd "$(dirname "$0")/.." || exit 1
echo sack > harness/CURRENT
L=results/audit/sack.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob
    local tag="r$1.$2.$3"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_ORDER="$2" OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/sack.log \
      && git commit -q -m "in-flight: sack $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
    for p in 16 6 20 1; do
        for k in rank sac1 sac3 sac5 sac8 sac16; do
            run $rep "$k" $p
        done
    done
    echo "REPDONE $rep" >> $L
done
echo "SACKDONE" >> $L
echo idle > harness/CURRENT

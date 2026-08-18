#!/bin/bash
# REBUILD THE AXIS PORTFOLIO ON SIGNALS THAT ARE NOT CORRELATED WITH EACH OTHER.
#
# Three measurements set this up, all in results/audit/.
#
# axes_structure.md: worker wid opens on _AXES[wid % 6] and nw = 4, so axes 4 and 5 can never open
# a run -- and the loop's own trace on the hidden P6 recorded the first beam producing the best
# solution of the entire 300 s run in 33 s.  The opening axis largely decides the answer, so the
# list is four entries in practice, and two of those four differ only by pos_lam 0.10 vs 0.12.
# Three distinct viewpoints across four opening slots.
#
# attractors.md: independent configurations return objectives equal to the digit -- prob_16 gave
# 3,656,247 from two runs differing in wid, seed, axis rotation AND per-worker budget.  The answer
# is a minimum over workers, so a portfolio is worth what its workers differ by, and workers built
# on correlated signals converge.
#
# And the signals ARE correlated: every shipped order is built from due, due - pt and area, with
# rho(area, due) = +0.23 over the forty stage-2 instances.
#
# Two geometric measures were then tested for orthogonality against area across all forty:
#     aspect ratio    rho = -0.053
#     box fill        rho = -0.061
# Both are effectively independent of size.  A first candidate -- short-axis lane occupancy --
# was tested first and REJECTED at rho = 0.88, which is why it is not in these sets.
#
# The arms fill the four opening slots one signal each:
#     o4    edd, lst, rank, aspect         deadline / slack / size / shape
#     o4f   edd, lst, rank, boxfill        the other shape signal in the same slot
#     o5    edd, lst, rank, aspect, boxfill
# Parameters come from the slots those orders already occupy rather than being invented.
#
# Smoke on prob_20 at 60 s: worker spread 55.1% against a base that runs 19-30% there, which is
# the mechanism doing what it is supposed to.  Whether wider workers give a better MINIMUM is the
# question here, and it does not follow -- cdecomp measured dispatch order changing construction by
# 32-210% while b240 found it not surviving to the final answer.
#
# Twelve instances drawn with a fixed seed, stratified by the w1/w3 exchange rate (4 low, 4 mid,
# 4 high) and by block count inside each band, because this session's earlier verdicts of "no
# effect" turned out to be opposite effects in different bands cancelling in the pool.
set -u
cd "$(dirname "$0")/.." || exit 1
echo ortho > harness/CURRENT
L=results/audit/ortho.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob axset
    local tag="r$1.$2.$3"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/ortho.log \
      && git commit -q -m "in-flight: ortho $tag" ) >/dev/null 2>&1
}

ORDER="20 2 4 6 1 13 32 5 31 26 38 35"
for rep in 1 2; do
    for p in $ORDER; do
        run $rep base $p ""
        run $rep o4   $p "OGC_AXSET=o4"
        run $rep o4f  $p "OGC_AXSET=o4f"
        run $rep o5   $p "OGC_AXSET=o5"
    done
    echo "REPDONE $rep" >> $L
done
echo "ORTHODONE" >> $L
echo idle > harness/CURRENT

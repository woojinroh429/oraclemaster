#!/bin/bash
# Old build vs new build, AND how wide each one's outcome spreads.  One experiment, because they
# are the same measurement.
#
# WHY THIS REPLACES BOTH harness/rebuild.sh's A/B AND harness/wspread.sh.
#
# rebuild.sh ran each instance once per arm.  That answers nothing here: run-to-run spread on an
# unchanged build has measured 3.2% to 32%, and three replicates of one build once spread 29.3%.
# Its first three pairs came back +0.005%, +4.6%, -1.70% -- which is exactly what noise looks like,
# and no amount of staring at three single draws separates it from a real effect.
#
# wspread.sh asked the other question -- where the bad draw is, and whether more draws remove it --
# and it needs the same thing: the same instance run many times.  Running both separately would
# pay for the replicates twice and would measure variance on a build with a known crash in it.
#
# So: both arms, several replicates, same instances, same budget.  From the same logs come the
# run-to-run spread per arm (the risk the score carries), the worst case per arm (the thing the
# request is actually about), the arm comparison judged on distributions rather than single draws,
# and -- from OGC_WSTAT -- the intra-round worker spread that says whether more draws can help.
#
# REP-MAJOR ORDER.  Every instance and both arms complete at replicate 1 before replicate 2 starts,
# so the log is a balanced dataset at every moment.  A container wipe or an early stop leaves a
# usable experiment instead of a deep sample of the first few instances and nothing about the rest.
# Within a replicate the two arms are adjacent, so drift in machine load hits both alike.
set -u
cd "$(dirname "$0")/.." || exit 1
R=$(pwd)
echo abvar > harness/CURRENT
L=results/audit/abvar.log
mkdir -p results/audit; touch $L

[ -x build_new/ogc_fast.cpython-312-x86_64-linux-gnu.so ] || [ -f build_new/ogc_fast.cpython-312-x86_64-linux-gnu.so ] || {
    echo "build_new is missing -- run harness/rebuild.sh first" >> $L; exit 1; }

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
    if [ "$2" = old ]; then
        OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 "[$tag]" \
            --data data/stage2 >> $L 2>&1
    else
        ( cd build_new && OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 \
            "[$tag]" --data data/stage2 ) >> $L 2>&1
    fi
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/abvar.log \
      && git commit -q -m "in-flight: abvar $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3 4 5; do
    for p in 1 12 16 26 6 3 20 30; do
        run $rep old $p
        run $rep new $p
    done
    echo "REPDONE $rep" >> $L
done
echo "ABVARDONE" >> $L
echo idle > harness/CURRENT

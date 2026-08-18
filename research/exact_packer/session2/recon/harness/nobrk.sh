#!/bin/bash
# VALIDATE THE no-brk SUBMISSION BUILD BEFORE IT GOES OUT, AND PRICE brk WHILE DOING IT.
#
# The build ships with bayrepack's operator unregistered (OGC_BRK=1 restores it), so the question
# to answer before submitting is not "is it better" -- that is what the hidden set is being asked
# -- but "is it SAFE": every instance still feasible, no hang, no crash, and the loss where it
# loses bounded rather than catastrophic.
#
# Paired against the same build with OGC_BRK=1, so the only difference is the operator, and across
# the exchange-rate range because this session established that pooling opposite-signed bands is
# how four earlier experiments came out as "no effect".
set -u
cd "$(dirname "$0")/.." || exit 1
echo nobrk > harness/CURRENT
L=results/audit/nobrk.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
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
      && git add research/exact_packer/session2/recon/results/audit/nobrk.log \
      && git commit -q -m "in-flight: nobrk $tag" ) >/dev/null 2>&1
}

ORDER="4 26 20 2 13 6 1 32 5 31 38 35"
for rep in 1 2; do
    for p in $ORDER; do
        run $rep withbrk $p "OGC_BRK=1"
        run $rep nobrk   $p ""
    done
    echo "REPDONE $rep" >> $L
done
echo "NOBRKDONE" >> $L
echo idle > harness/CURRENT

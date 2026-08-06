#!/bin/bash
# THE TWO-PHASE AIM RACE AGAINST THE SHIPPED BUILD.
#
# What is being bought: the beam aim is fixed at fork (the C++ reads OGC_BEAMAIM once per process
# into a static) and on some instances it decides the run -- P16's losing half is 33-41% behind,
# P36's is 17% behind at every one of six budgets, P34's is 17% behind with the OTHER aim winning.
# Both P34 and P36 are 300-block instances, so nothing readable off the instance predicts it.  So
# half the cores burn the whole budget on a draw that was never going to be the minimum.
#
# OGC_RACE=1 spends a short phase 1 (OGC_RACEF, default 25% of the worker budget) finding out
# which aim leads HERE, then respawns every worker on the winner for the rest.  `best` spans both
# phases, so the incumbent cannot be lost, and the minimum is over 2*nw draws instead of nw.
#
# What it costs: phase 2 has 75% of the depth.  That is not free -- redrawing a worker in place
# was tried first and failed for exactly this reason (a worker restarted at 60% could not beat its
# own earlier deep draw, twice, to the digit).  So this is close arithmetic: 4 draws at 75% depth
# against 2 useful draws at 100%, and it has to be run rather than argued.
#
# Smoke, P16 at 120 s: phase 1 read 0.10=3,057,910 against 0.90=4,313,094 and the run returned
# 3,044,330 -- equal to the best 240 s base draw on record, at half the budget.  One draw, on the
# instance with the widest aim gap and a 25% spread of its own; that is a reason to measure, not
# a result.
#
# Eight instances spanning the aim behaviour we know (P16 widest gap, P36 and P34 opposite
# winners, P26/P30 from the cliff ladder) and three replicates, because a single pair cannot be
# read against a per-instance spread this wide.
set -u
cd "$(dirname "$0")/.." || exit 1
echo race > harness/CURRENT
L=results/audit/race.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env mod
    local tag="r$1.$2.$3"
    grep -q "\[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py $5 $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/race.log \
      && git commit -q -m "in-flight: race $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 16 36 34 6 20 1 26 30; do
        run $rep base $p ""           myalgorithm
        run $rep race $p "OGC_RACE=1" myalg_race
    done
    echo "REPDONE $rep" >> $L
done
echo "RACEDONE" >> $L
echo idle > harness/CURRENT

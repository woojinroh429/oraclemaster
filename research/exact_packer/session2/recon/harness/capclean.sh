#!/bin/bash
# OGC_BEAMCAP, RE-MEASURED ON A BUILD WHOSE BASELINE MATCHES THE RECORD.
#
# Why this repeats a queue that already ran.  beamcap's rep 1 was measured on a build carrying the
# DRAWSTAT instrumentation, and that instrumentation was not free: one time.time() and one _jit()
# call per draw, both behind flags that were OFF, moved prob_24 from 2,809,182 -- the value three
# earlier queues returned to the digit on the identical configuration -- to 2,838,115, with Z1, Z2
# and Z3 all different.  Removing the two dead calls restored 2,809,182 exactly (Z1=656, Z2=2562,
# Z3=1008).  ogc_fast recomputes its beam width from elapsed()/work at every one of ~250 levels,
# so microseconds of drift pick a different trajectory.
#
# The arms in that queue all shared the contamination, so their comparison stands:
#
#     cap12   min -1.04% (better 2/4)   median worker -0.98% (better 3/4)
#     cap20   min -1.81% (better 2/4)   median worker -1.29% (better 3/4)
#
# and the median-worker column is what makes it interesting -- an arm that moves the minimum but
# not the median worker got a lucky draw, and both arms moved both.  What it cannot support is a
# decision: n=1 per cell, against a prob_16 run-to-run difference of 3.5% on the SAME settings.
#
# So: same arms, clean build, two replicates.  prob_24 is now a real control -- its baseline was
# verified minutes ago at 2,809,182 on this exact build, so anything that moves there is the cap.
#
# NOT USED AS EVIDENCE: the spread column.  spread is (max-min)/min and the score IS min, so an
# arm that lowers the minimum raises the spread by arithmetic.  This project has already withdrawn
# eight conclusions built on that correlation (results/audit/spread_artifact.md).  Judge on the
# minimum and on the median worker only.
#
# Read with:  python3.12 harness/beamside.py results/audit/capclean.log base
set -u
cd "$(dirname "$0")/.." || exit 1
echo capclean > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=capclean" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/capclean.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 1200 /usr/bin/python3.12 harness/run1.py myalgorithm \
        $3 240 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/capclean.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: capclean $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
    for p in 24 16 4 20; do
        run $rep base  $p ""
        run $rep cap12 $p "OGC_BEAMCAP=12"
        run $rep cap20 $p "OGC_BEAMCAP=20"
    done
    echo "REPDONE $rep" >> $L
done
echo "CAPCLEANDONE" >> $L
# then the spread arms, which the cap result feeds into: if narrow draws win by raising the
# left tail, OGC_ADAPTB=0 and OGC_AXJIT should win for the same reason and by more.
echo spread > harness/CURRENT
nohup bash harness/spread.sh >> results/spread.log 2>&1 < /dev/null &

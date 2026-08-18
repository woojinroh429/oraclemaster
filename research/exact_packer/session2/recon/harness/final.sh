#!/bin/bash
# THE RESERVE A/B, RE-RUN ON THE ENGINE THAT ACTUALLY SHIPS.
#
# Every earlier experiment imported the recon directory's .so, dated 2026-08-07.  The submission
# compiles its five engines from the .cpp in that same directory, and the dirgate zip and today's
# zip carry byte-identical binaries -- so the build is reproducible and the repo's differing .so
# were a stale source state, not a rebuild artefact.  The extensions have now been rebuilt in place
# and all five md5-match the zip's.  This is the first measurement on the shipped engine.
#
# IT MATTERS BECAUSE THE ENGINE MOVED THE BASELINE, NOT JUST THE NOISE:
#     P1, RESFRAC 0.50, nw=3   stale     688,254 / 708,344 / 754,716
#                              shipped   508,193 / 518,660 / 605,585
# The shipped engine is ~30% better on P1 at the OLD setting, which is most of what the reserve
# change appeared to buy on the stale one.
#
# ARMS: A = RESFRAC 0.50 (what is submitted), B = RESFRAC 0.05.  Nothing else varies.  No WORKERS
# in the environment, so nw = cpu_count-1 = 3 exactly as the grader runs it.
#
# JUDGED, fixed before the run: three draws per cell, paired within replicate, ratio-mean and
# geometric mean across the six firing instances.  B ships only if it wins the ratio-mean AND does
# not lose P1, which is the instance the submission is being played for.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo final > harness/CURRENT
L=results/audit/final.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/final.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/final.sh \
        && git commit -q -m "in-flight: final $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3 27 16 7 33; do
    run "A.p$p.r$rep" $p "OGC_RESFRAC=0.50"
    run "B.p$p.r$rep" $p "OGC_RESFRAC=0.05"
  done
done
echo "FINALDONE" >> $L
echo idle > harness/CURRENT

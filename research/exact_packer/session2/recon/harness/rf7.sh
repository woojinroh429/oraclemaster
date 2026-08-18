#!/bin/bash
# THE RESERVE AT THE WORKER COUNT THE GRADER ACTUALLY RUNS.
#
# RESFRAC 0.05 was the strongest single change this study produced -- 18 cells of 18 at nw=3,
# ratio-mean -17.36% (wdef.log), and it shipped inside OGC2026_capfix.zip together with the CPU cap.
# The scoreboard rejected that build: 74,330,722 against dirgate's 72,188,856.  The per-group split
# blamed the cap -- the reserve can only reach instances inside the direction gate's band, of which
# the hidden set holds one or two, and yet the other six worsened 2.11%.
#
# THE RESERVE WAS THEN REVERTED ON REASONING, NOT MEASUREMENT: every cell behind -17.36% was taken
# at nw=3, which is what the cap produces, so without the cap the grader runs seven workers and the
# evidence "does not transfer".  That was an assumption and it is testable in one line.
#
# IT IS WRONG.  prob_1, 60 s, WORKERS=7, one draw each:
#
#     RESFRAC 0.50   695,860   ran 36 s of 60      24 seconds never used
#     RESFRAC 0.05   643,216   ran 58 s of 60      -7.6%
#
# The idle-budget defect the reserve change was built for exists at seven workers too.  The polish
# returns almost immediately whatever the worker count is, so the reserve is dead time either way.
#
# IF THIS HOLDS, THE SCOREBOARD READS CLEANLY: capfix's +2.97% was the cap alone, and the reserve
# belongs in the build WITHOUT it -- which is a change that costs nothing and was measured, unlike
# the cap, which cost 2.11% on the instances only it could reach.
#
# WHAT WOULD MAKE IT FAIL, named first.  One draw at 60 s on prob_1 is worth very little: that
# instance spanned 508k-712k across today's draws on unchanged builds, and 695,860 vs 643,216 sits
# inside that range.  Six draws paired, and prob_3 and prob_16 to check it is not prob_1's alone.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo rf7 > harness/CURRENT
L=results/audit/rf7.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/rf7.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/rf7.sh \
        && git commit -q -m "in-flight: rf7 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" rf="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env WORKERS=7 OGC_RESFRAC=$rf timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3 4 5 6; do
  run "r.p1.50.r$rep" 1 0.50
  run "r.p1.05.r$rep" 1 0.05
done
for rep in 1 2 3; do
  for p in 3 16 2 13; do
    run "r.p$p.50.r$rep" $p 0.50
    run "r.p$p.05.r$rep" $p 0.05
  done
done
echo "RF7DONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# THE PERMUTATION IS THE LARGEST LEVER ON THIS PROBLEM AND IT HAS ONE THIRD OF THE PORTFOLIO.
#
# ogc_fast.cpp, at the level loop:
#   "The permutation is the largest lever measured on this problem -- cdecomp put the construction
#    spread across orders at 32-210%, against about 2% for the combined range of budget policy,
#    axis sets, the w3mul grid and brk removal."
#
# OGC_MCAND is what opens that dimension: each state expands the M earliest UNPLACED blocks instead
# of only order[level], so states diverge in which blocks they have placed rather than only in where
# they put the same ones.  M=1 is the old behaviour exactly.  The shipped default is OGC_MSET="1,2"
# indexed by wid%2, so at nw=3 two workers run M=1 and one runs M=2.
#
# EVERYTHING MEASURED TODAY LIVED INSIDE THAT 2%.  RESFRAC, ROUNDS, w3mul, brk, the probe cap and
# the gain fix moved the band by single digits at best.  This knob is the one the file's own
# measurements call an order of magnitude larger.
#
# AND IT IS NOW MEASURABLE WITHOUT NOISE.  OGC_WORKCAP replaces the clock with states-expanded in
# the width controller and the stop test, so a build/instance/cap triple returns the same answer
# every time -- verified here: three identical runs of prob_1 all returned 568,924 to the digit,
# against the 17-35% run-to-run spread every wall-clock experiment today had to fight.
#
# WORKCAP=5000 binds (prob_1: 492,458, 65 s); 20000 and 80000 do not (568,924, 85 s).
#
# PHASE 1, HERE: quality per unit of work.  work += nbeam*M per level, so a larger M costs
# proportionally more work and reaches fewer levels before the cap -- which is exactly the trade
# being measured.  One draw per cell is enough because the cell is deterministic.
#
# PHASE 2, SEPARATE: throughput at wall clock.  The file prescribes the two-part evaluation --
# equal-work A/B, then how much work each arm completes in the real budget, then quality at
# work = throughput x budget.  Phase 1 alone cannot decide a shipping value.
#
# WORKERS=1 so M is unambiguous and the pool's deadline cannot truncate anything.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo mcand > harness/CURRENT
L=results/audit/mcand.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/mcand.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/mcand.sh \
        && git commit -q -m "in-flight: mcand $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" m="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env OGC_WORKCAP=5000 WORKERS=1 OGC_MCAND=$m timeout 300 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for p in 1 3 16 13; do
  for m in 1 2 3 4 6 8; do
    run "m.p$p.m$m" $p $m
  done
done
echo "MCANDDONE" >> $L
echo idle > harness/CURRENT
